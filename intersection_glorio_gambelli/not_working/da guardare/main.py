from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import optparse
import random

# we need to import python modules from the $SUMO_HOME/tools directory
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

from sumolib import checkBinary  # noqa
import traci  # noqa

lanes = ['e01_05_0', 'e01_05_1',
         'e02_05_0', 'e02_05_1',
         'e03_05_0', 'e03_05_1',
         'e04_05_0', 'e04_05_1',
         'e05_01_0', 'e05_01_1',
         'e05_02_0', 'e05_02_1',
         'e05_03_0', 'e05_03_1',
         'e05_04_0', 'e05_04_1',
         ]

crossingStatus = {}

partecipants = []

partecipantsRoutes = {}

possibleRoutes = {}

vehiclesInAuction = []

nonStoppedVehicles = []

winners = []

winnersLanes = {}

currentWinners = []

losers = []

currentLosers = []

precedences = {}


def getVehiclesAtJunction():
    """Funzione che restituisce tutti i veicoli che viaggiano verso un incrocio"""
    vehiclesAtJunction = []
    for l in lanes:
        if int(l[1:3]) != 5:  # si lavora sui veicoli che viaggiano verso l'incrocio
            vehiclesAtJunction += reversed(traci.lane.getLastStepVehicleIDs(l))
    return vehiclesAtJunction


def isFrontalTrajectory(vehicle):
    """Funzione che restituisce True se il veicolo passato in argomento deve andare dritto, False altrimenti"""
    route = traci.vehicle.getRoute(vehicle)
    currentEdge = (int(route[0][1:3]), int(route[0][4:6]))
    nextEdge = (int(route[1][1:3]), int(route[1][4:6]))
    if abs(currentEdge[0] - currentEdge[1]) == abs(nextEdge[0] - nextEdge[1]):
        return True
    return False


def fromEdgesToLanes(vehicle):
    """Funzione utilizzabile per ottenere la route, composta di lanes, che un veicolo deve seguire per attraversare
    correttamente l'incrocio."""
    route = vehicle.getCurrentRoute()
    currentLane = traci.vehicle.getLaneID(vehicle.getID())[-1]
    currentEdge = (int(route[0][1:3]), int(route[0][4:6]))
    nextEdge = (int(route[1][1:3]), int(route[1][4:6]))
    if abs(currentEdge[0] - currentEdge[1]) == abs(nextEdge[0] - nextEdge[1]):
        return f'{route[0]}_{currentLane}', f'{route[1]}_{currentLane}'
    lane0 = f'{route[0]}_0'
    lane1 = f'{route[0]}_1'
    laneBase = ''
    laneObjective = ''
    for direction, lane in possibleRoutes[lane0].items():
        if lane[:-2] == route[1]:
            laneBase = lane0
            laneObjective = lane
            break
    if laneBase == '':
        for direction, lane in possibleRoutes[lane1].items():
            if lane[:-2] == route[1]:
                laneBase = lane1
                laneObjective = lane
                break
    return laneBase, laneObjective


def updateCrossingStatus(vehicles):
    """Funzione che trova i veicoli attualmente in testa ad ogni corsia. Questi saranno i veicoli papabili per un
    attraversamento"""
    # con il seguente ciclo determino i veicoli attualmente in testa alle corsie che vanno verso l'incrocio
    vehiclesInHead = []
    otherVehicles = []
    incomingLanes = lanes[0:8]
    for lane in incomingLanes:
        # il veicolo più vicino all'incrocio è quello indicato all'ultima posizione della lista ottenuta attraverso
        # la funzione traci.lane.getLastStepVehicleIDs(idLane)
        laneQueueTemp = traci.lane.getLastStepVehicleIDs(lane)
        laneQueue = []
        for j in laneQueueTemp:
            # try che gestisce un errore che può verificarsi dopo il superamento della soglia di fine simulazione,
            # per cui dei veicoli potrebbero ancora trovarsi nella simulazione e quindi essere restituiti da traci
            # pur essendo già stati rimossi da tutte le altre strutture dati.
            try:
                laneQueue.append(vehicles[j])
            except:
                pass
        # prendendo l'ultimo veicolo seleziono quello in testa alla corsia.
        if laneQueue:
            # self.crossingStatus[i] = vehicles[laneQueue[-1]]
            crossingStatus[lane] = laneQueue[-1]
            vehiclesInHead.append(laneQueue[-1])
            otherVehicles += laneQueue[:-1]
        else:
            crossingStatus[lane] = None
    vehiclesPassed = []
    for i in partecipants:
        # visto che questo ciclo passa in rassegna tutti i veicoli ad un incrocio ho aggiunto queste 2 righe che
        # impediscono ad un veicolo di cambiare corsia nel momento in cui si trovano troppo vicini all'incrocio
        # TODO: da tenere?
        if not i.isSlowed:
            i.isSlowed = True
            traci.vehicle.slowDown(i.getID(), 3, 3)  # TODO: 8 o 4?
        if i.isAllowedLaneChange() and i.distanceFromEndLane() < 15:
            i.forbidLaneChange()
        # print('control', traci.vehicle.getLaneID(i.getID())[1:3], self.junction.getNumericID())
        # se il veicolo si trova su una corsia il cui primo numero indicato è quello dell'id dell'incrocio allora
        # il veicolo si trova su di una corsia uscente e può essere rimosso dal crossing manager
        if traci.vehicle.getLaneID(i.getID()):
            if traci.vehicle.getLaneID(i.getID())[0] == 'e' and \
                    int(traci.vehicle.getLaneID(i.getID())[1:3]) == 5:
                vehiclesPassed.append(i)
    for i in vehiclesPassed:
        partecipants.remove(i)
        """codice utilizzato per la distribuzione del traffico."""
        if isFrontalTrajectory(i):
            currentLane = int(i.getCurrentLane()[-1])
            newLane = 0 if currentLane == 1 else 1
            nlaneID = list(i.getCurrentLane())
            nlaneID[-1] = str(newLane)
            nlaneID = ''.join(nlaneID)
            if len(traci.lane.getLastStepVehicleIDs(i.getCurrentLane())) >= 2 * len(
                    traci.lane.getLastStepVehicleIDs(nlaneID)):
                currentLane = int(i.getCurrentLane()[-1])
                newLane = 0 if currentLane == 1 else 1
                traci.vehicle.changeLane(i.getID(), newLane, 10)
                i.forbidLaneChange()
    for i in partecipants:
        if traci.vehicle.getLaneID(i.getID())[0] == 'e':
            # if traci.vehicle.getLaneID(i.getID())[0] == 'e':
            partecipantsRoutes[i] = fromEdgesToLanes(i)


def updateVehicleStatus(vehicle):
    """Funzione che aggiorna i permessi di passaggio per un veicolo che debba attraversare ma che non possa entrare
    in un'asta. I veicoli non possono entrare in un'asta in 2 casi: o dovrebbero parteciparvi con soli veicoli
    vincitori (i veicoli vincitori non prendono più parte ad aste) oppure non necessitano di competere, hanno solo
    bisogno di un permesso di passaggio."""
    pass


def saveAuctionResults():
    """Funzione utilizzata per salvare i risultati di un'asta nel caso di non bufferizzazione e quindi di non
    necessità di un merge dei vincitori. Evita di utilizzare la struttura delle precedenze, in modo da risparmiare
    complessità computazionale."""
    winnersLanes[winners[0].getCurrentLane()] = winners
    for i in winners:
        if i not in partecipants:
            partecipants.append(i)
            if not i.isStopped():
                i.stopVehicle()
            partecipantsRoutes[i] = fromEdgesToLanes(i)
        if i in currentLosers:
            currentLosers.remove(i)
            vehiclesInAuction.remove(i)
        currentWinners.append(i)
        vehiclesInAuction.append(i)
        precedences[i] = losers
    for i in losers:
        currentLosers.append(i)
        vehiclesInAuction.append(i)
        partecipantsRoutes[i] = fromEdgesToLanes(i)
        i.nVehiclesToWait += len(winners)
        if i not in partecipants:
            partecipants.append(i)
            if not i.isStopped():
                i.stopVehicle()
            precedences[i] = []


def getVehiclesNowCrossing():
    """Funzione che restituisce i veicoli in fase di attraversamento."""
    vehiclesCrossing = []
    for i in partecipants:
        if i.getCurrentLane()[:4].replace('_', '') == f':n5':
            vehiclesCrossing.append(i)
    return vehiclesCrossing


def allowCrossing_nonBuffered():
    """Funzione che concede effettivamente la capacità di movimento ai veicoli schedulati per il passaggio."""
    vehiclesInHead = [i for i in crossingStatus.values() if i is not None and
                      i.distanceFromEndLane() <= 15 and i not in nonStoppedVehicles]
    # con il seguente ciclo rimuoviamo dalla corsia dei vincitori i veicoli che hanno cominciato ad attraversare la
    # l'incrocio
    for wv in currentWinners:
        lane = partecipantsRoutes[wv][0]
        if lane in winnersLanes:
            if wv in winnersLanes[lane] and wv in getVehiclesNowCrossing():
                winnersLanes[lane].remove(wv)
            if not winnersLanes[lane]:
                winnersLanes.pop(lane)
    winningVehicles = [i for i in currentWinners if i in vehiclesInHead]
    for wv in winningVehicles:
        wv.restartVehicle()
        nonStoppedVehicles.append(wv)
        """Salvo i tempi di attesa"""
        if not wv.hasPassedFreely:
            wv.saveTimePassedAtJunction()
            wv.saveMainGroupWaitingTime()
            wv.saveTotalWaitingTime()
        wv.resetJunctionWaitingTime()
        wv.resetTotalWaitingTime()
        wv.resetMainGroupWaitingTime()

    # ricreiamo veh in head perchè alcuni veicoli potrebbero dover essere rimossi
    vehiclesInHead = [i for i in crossingStatus.values() if i is not None and
                      i.distanceFromEndLane() <= 15 and i not in nonStoppedVehicles]


def allowCrossing():
    """Funzione che, dopo aver controllato i veicoli nelle posizioni di testa, da il via libera ai veicoli che, nel
    passare, non risultano essere in traiettorie incidentali, rispettando la lista delle precedenze dei veicoli"""
    # prendo i veicoli in testa poichè sono gli unici che possono passare all'atto pratico
    vehiclesInHead = [i for i in crossingStatus.values() if i is not None and i in precedences
                      and i.distanceFromEndLane() <= 15]
    vehiclesCrossing = getVehiclesNowCrossing()
    allowCrossing_nonBuffered()


def createAuction(idVeh, vehicles):
    """Funzione che permette di aggiungere un'asta all'elenco di quelle attualmente in corso nell'incrocio
       :param idVeh: ID del veicolo di cui si cercheranno i rivali.
       :param vehicles: veicoli raggruppati per corsia d'appartenenza;"""
    """Ramo importante della funzione."""
    lp = []
    ls = []
    """Se è variabile otterrò una dimensione dipendente dal numero di veicoli in corsia."""
    maxLength = self.maxDimensionCalc(idVeh.getCurrentLane())
    # print('trying auction', idVeh.getID())
    """Ciclo sulla reversed del getLastStepVehicleIDs() per selezionare prima i veicoli più vicini 
    all'incrocio."""
    for veh in reversed(traci.lane.getLastStepVehicleIDs(idVeh.getCurrentLane())):
        veh = vehicles[veh]
        # print(f'conditions on {veh.getID()} ({veh.getCurrentLane()}): posizione {veh.checkPosition(self)}, '
        #       f'auction {veh not in self.crossingManager.vehiclesInAuction}, veicoli riattivati {veh not in self.crossingManager.nonStoppedVehicles}, '
        #       f'distanza {veh.distanceFromEndLane() < 40}, maxLength {len(lp) < maxLength}')
        if veh.checkPosition(self) and veh not in vehiclesInAuction \
                and veh not in nonStoppedVehicles:
            if veh.distanceFromEndLane() < 40 and len(lp) < maxLength:
                lp.append(veh)
                # print(f'adding {veh.getID()} to lp')
            else:
                ls.append(veh)
                # print(f'adding {veh.getID()} to ls')

    clashingLists = [[lp, ls]]
    clashingVehicles = [idVeh]
    vehiclesInHead = [i for i in crossingStatus.values() if i is not None
                      and i not in vehiclesInAuction
                      and i not in nonStoppedVehicles
                      and i.distanceFromEndLane() < 15 and i.checkPosition(self)]

    """Cerco i veicoli in traiettoria incidentale con quelli pronti a partecipare all'asta."""
    for veh in clashingVehicles:
        # print('veh subject', veh.getID(), veh.getCurrentRoute())
        # print(f'subject {veh.getID()} ({veh.getCurrentLane()})')
        for otherVeh in vehiclesInHead:
            # print(f'object {otherVeh.getID()} ({otherVeh.getCurrentLane()}), condizioni: diversità {otherVeh != veh}, non presenza '
            #       f'{otherVeh not in clashingVehicles}, clashing {self.isClashing(self.fromEdgesToLanes(veh), self.fromEdgesToLanes(otherVeh))}')
            if otherVeh != veh and otherVeh not in clashingVehicles:
                if self.isClashing(self.fromEdgesToLanes(veh),
                                   self.fromEdgesToLanes(otherVeh)):
                    clashingVehicles.append(otherVeh)
                    vlp = []
                    vls = []
                    maxLength = self.maxDimensionCalc(otherVeh.getCurrentLane())
                    for v in reversed(traci.lane.getLastStepVehicleIDs(otherVeh.getCurrentLane())):
                        v = vehicles[v]
                        # print(
                        #     f'conditions on {v.getID()} ({v.getCurrentLane()}): posizione {v.checkPosition(self)}, '
                        #     f'auction {v not in self.crossingManager.vehiclesInAuction}, veicoli riattivati {v not in self.crossingManager.nonStoppedVehicles}, '
                        #     f'distanza {v.distanceFromEndLane() < 40}, maxLength {len(vlp) < maxLength}')
                        if v.checkPosition(self) and v not in vehiclesInAuction \
                                and v not in nonStoppedVehicles:
                            if v.distanceFromEndLane() < 40 and len(vlp) < maxLength:
                                vlp.append(v)
                                # print(f'adding {veh.getID()} to vlp')
                            else:
                                vls.append(v)
                                # print(f'adding {veh.getID()} to vls')
                    if vlp:
                        clashingLists.append([vlp, vls])
    # print('number of clashing lists', len(clashingLists))
    # cLLength = len(clashingLists)
    # blockingVehicles = []

    # ######################################################################################################## #
    """Blocco di codice che impedisce ai veicoli in traiettoria incidentale con l'insieme dei bloccanti di 
    prendere parte alle aste. Tutti i veicoli dopo un veicolo che non può prendere parte ad un'asta vengono
    messi insieme ad esso nel gruppo degli sponsors."""
    if self.isCompetitive:
        # for cl in clashingLists:
        #     print('p c l v: ', end='')
        #     for v in cl[0]:
        #         print(v.getID(), v.getCurrentLane(), end=', ')
        #     print()
        """Caso competitivo. Con questo ciclo individuiamo eventuali veicoli in clash con veicoli vincitori 
        e gli impediamo di prendere parte all'asta. L'asta non viene permessa nemmeno ai veicoli che vengono 
        dopo il veicolo in clash."""
        if currentWinners:
            blockingVehicles = currentWinners.copy()
            # blockingVehicles.extend(i for i in self.crossingManager.nonStoppedVehicles if i not in blockingVehicles)
            listsToBeRemoved = []
            for cl in clashingLists:
                vehToBeRemoved = []
                for veh in cl[0]:
                    isInAClash = False
                    for bv in blockingVehicles:
                        # print(f'bv {bv.getID()}, ({bv.getCurrentLane()})')
                        # se trovo un veicolo in clash con un vincitore
                        if self.isClashing(fromEdgesToLanes(veh), partecipantsRoutes[bv]):
                            isInAClash = True
                            # lo rimuovo insieme a tutti i veicoli vengono dopo di lui
                            vehToBeRemoved = cl[0][cl[0].index(veh):]
                            break
                    if isInAClash:
                        for v in vehToBeRemoved:
                            cl[0].remove(v)
                        if not cl[0]:
                            # se non ci sono più veicoli rimuoviamo la lista
                            listsToBeRemoved.append(cl)
                        else:
                            # aggiungiamo i veicoli che non possono direttamente partecipare all'asta all'elenco
                            # degli sponsor.
                            cl[1].extend(vehToBeRemoved)
                        break
            for li in listsToBeRemoved:
                clashingLists.remove(li)
    else:
        # for cl in clashingLists:
        #     print('p c l v: ', end='')
        #     for v in cl[0]:
        #         print(v.getID(), v.getCurrentLane(), end=', ')
        #     print()
        """Caso cooperativo. Con questo ciclo individuiamo eventuali veicoli in clash con veicoli che hanno 
        preso precedentemente parte ad un'asta. L'asta non viene permessa nemmeno ai veicoli che vengono dopo
         il veicolo in clash."""
        if self.crossingManager.orderedCooperativeList:
            blockingVehicles = [x for j in self.crossingManager.orderedCooperativeList for i in j for x in i]
            # print(f'bv {self.getID()} {[x.getID() for x in blockingVehicles]}')
            # if len(blockingVehicles) > 2:
            # blockingVehicles.extend(i for i in self.crossingManager.nonStoppedVehicles if i not in blockingVehicles)
            listsToBeRemoved = []
            for cl in clashingLists:
                vehToBeRemoved = []
                for veh in cl[0]:
                    isInAClash = False
                    for bv in blockingVehicles:
                        # print(f'bv {bv.getID()}, ({bv.getCurrentLane()})')
                        # meccanismo uguale al caso competitivo, guarda quei commenti
                        if self.isClashing(self.fromEdgesToLanes(veh), self.crossingManager.partecipantsRoutes[bv]):
                            isInAClash = True
                            vehToBeRemoved = cl[0][cl[0].index(veh):]
                            break
                    if isInAClash:
                        for v in vehToBeRemoved:
                            cl[0].remove(v)
                        if not cl[0]:
                            listsToBeRemoved.append(cl)
                        else:
                            # aggiungiamo i veicoli che non possono direttamente partecipare all'asta all'elenco
                            # degli sponsor.
                            cl[1].extend(vehToBeRemoved)
                        break
            for li in listsToBeRemoved:
                clashingLists.remove(li)
    if len(clashingLists) > 1:
        saveAuctionResults(auction)


def run(simulationMode=True, instantPay=True, routeMode=True, dimensionOfGroups=1,
        numberOfVehicles=1000, numberOfSteps=500):
    """Inserimento delle informazioni per il setup della simulazione"""
    choice = ''
    while choice not in ['s', 'S', 'd', 'D']:
        choice = input('Le route devono essere statiche o dinamiche? [s = statiche, d = dinamiche]\n: ')
        if choice not in ['s', 'S', 'd', 'D']:
            print('Inserire un carattere fra s e d')
    routeMode = True if choice in ['s', 'S'] else False
    choice = ''
    while choice not in [str(i) for i in range(1, 8)] + ['-1']:
        choice = input('Quale dimensione deve avere il numero di veicoli considerato? Per usare dimensioni '
                       'proporzionali inserire -1,\n'
                       '(i gruppi possono avere una dimensione che va da 1 a 7): ')
        if choice not in [str(i) for i in range(1, 8)] + ['-1']:
            print('Inserire un numero fra 1 e 7, oppure -1')
    dimensionOfGroups = int(choice)
    while True:
        try:
            choice = int(input('Quanti veicoli deve avere la simulazione?: '))
            break
        except:
            print('Inserire un numero intero')
    numberOfVehicles = choice
    while True:
        try:
            choice = int(input('Quanti step deve avere la simulazione?: '))
            break
        except:
            print('Inserire un numero intero')
    numberOfSteps = choice
    traci.start([sumoBinary, "-c", "intersection.sumocfg", "--time-to-teleport", "-1"])
    vehicles = {}  # dizionario contente dei riferimenti ad oggetto: idVx: Vehicle(x)
    """Con il seguente ciclo inizializzo i veicoli e gli assegno una route generata casualmente"""
    for i in range(1, numberOfVehicles + 1):
        listOfChoice = [1, 2, 3, 4]
        start = random.choice(listOfChoice)
        listOfChoice.remove(start)
        end = random.choice(listOfChoice)
        traci.route.add(f'{i}', [f'e0{start}_05', f'e05_0{end}'])
        traci.vehicle.add(f'{i}', f'{i}')
    """Ciclo che si limita ad assegnare un colore ai veicoli, per renderli distinguibili nella simulazione"""
    for i in range(1, numberOfVehicles + 1):
        if i % 8 == 1:
            traci.vehicle.setColor(f'{i}', (0, 255, 255))  # azzurro
        if i % 8 == 2:
            traci.vehicle.setColor(f'{i}', (160, 100, 100))  # rosa
        if i % 8 == 3:
            traci.vehicle.setColor(f'{i}', (255, 0, 0))  # rosso
        if i % 8 == 4:
            traci.vehicle.setColor(f'{i}', (0, 255, 0))  # verde
        if i % 8 == 5:
            traci.vehicle.setColor(f'{i}', (0, 0, 255))  # blu
        if i % 8 == 6:
            traci.vehicle.setColor(f'{i}', (255, 255, 255))  # bianco
        if i % 8 == 7:
            traci.vehicle.setColor(f'{i}', (255, 0, 255))  # viola
        if i % 8 == 8:
            traci.vehicle.setColor(f'{i}', (255, 100, 0))  # arancione
    """Di seguito inizializzo gli incroci che fanno parte della simulazione, assegnando loro una classe che ne descriva
        il comportamento specifico (o incroci a 3 strade o a 4 strade). Solo gli incroci a 4 strade sono stati usati nelle 
        simulazioni finali."""
    # junctions = []  # dovrà contenere l'incrocio centrale
    # junctions.append(FourWayJunction(5, vehicles, iP=instantPay, sM=simulationMode, bM=False,
    #                                  groupDimension=dimensionOfGroups))
    """Di seguito il ciclo entro cui avviene tutta la simulazione, una volta usciti la simulazione è conclusa"""
    step = 0
    while traci.simulation.getMinExpectedNumber() > 0 and step < numberOfSteps:
        traci.simulationStep()
        step += 1
        # """Ciclo principale dell'applicazione"""
        # for junction in junctions:
        """Prime operazioni sull'incrocio"""
        vehAtJunction = getVehiclesAtJunction()
        updateCrossingStatus(vehicles)
        # Prendo i tempi dei veicoli qualora fossero costretti a fermarsi
        vehiclesInHead = crossingStatus.values()
        """Flusso principale"""
        for idVeh in vehAtJunction:
            if idVeh in vehicles:
                objVeh = vehicles[idVeh]
                if objVeh.distanceFromEndLane() < 50:
                    if objVeh not in partecipants:
                        updateVehicleStatus(objVeh)
                    if objVeh.distanceFromEndLane() < 15:
                        """Ramo d'interesse"""
                        if objVeh in crossingStatus.values() and objVeh not in \
                                vehiclesInAuction and objVeh not in nonStoppedVehicles:
                            createAuction(objVeh, vehicles)
        if len(vehAtJunction) > 0:
            allowCrossing()


if __name__ == "__main__":
    choice = ''
    while choice not in ['d', 'D', 'g', 'G']:
        choice = input('Vuoi raccogliere dati o avere una visualizzazione grafica? [d = dati, g = grafica]\n: ')
        if choice not in ['d', 'D', 'g', 'G']:
            print('Inserire un carattere fra d e g')
    if choice in ['d', 'D']:
        sumoBinary = checkBinary('sumo')
    else:
        sumoBinary = checkBinary('sumo-gui')
    run(True, True, True, 1, 1000, 500)
