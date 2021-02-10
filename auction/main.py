import sys
import os
import random
from math import sqrt

from auction.trafficElements.junction import FourWayJunction
from auction.trafficElements.vehicle import Vehicle

from sumolib import miscutils
import traci

config_file = "intersection.sumocfg"  # file di configurazione della simulazione
junction_id = 7  # id dell'incrocio
lanes = []  # lista dei nomi delle lane
lanes_ids = [0, 2, 4]  # lista degli id delle lanes nell'incrocio
node_ids = [2, 8, 12, 6]  # lista degli id dei nodi di partenza e di groupsivo nell'incrocio
period = 10  # tempo di valutazione del throughput del sistema incrocio

"""Con questo ciclo inizializzo i nomi delle lane"""

for i in node_ids:
    for lane in lanes_ids:
        lanes.append(f'e{"0" if i < 12 else ""}{i}_0{junction_id}_{lane}')
        lanes.append(f'e0{junction_id}_{"0" if i < 12 else ""}{i}_{lane}')


def getLaneFromEdges(node_ids, start, end):
    """Funzione che trova la lane corretta da far seguire al veicolo dati il nodo di partenza e quello di
    destinazione"""

    distance = -1
    i = 0
    trovato = False
    while True:
        if node_ids[i % 4] == start:
            trovato = True
        if trovato:
            distance += 1
            if node_ids[i % 4] == end:
                break
        i += 1
    lane = 0
    if distance == 1:
        lane = 4
    if distance == 2:
        lane = 2
    if distance == 3:
        lane = 0
    return lane


def getDistanceFromLaneEnd(spawn_distance, lane_length, shape):
    """Calcolo la distanza tra il veicolo e l'inizio dell'incrocio"""

    min_x = shape[0][0]
    max_x = shape[0][0]
    for point in shape:
        if point[0] < min_x:
            min_x = point[0]
        if point[0] > max_x:
            max_x = point[0]
    lane_end = lane_length - (max_x - min_x) / 2
    return lane_end - spawn_distance


def run(numberOfVehicles, schema, sumoCmd, simulationMode, instantPay, dimensionOfGroups, path, index, queue):
    """Funzione che avvia la simulazione dato un certo numero di veicoli"""

    port = miscutils.getFreeSocketPort()

    dir = os.path.join(path, 'terminals')

    if not os.path.exists(dir):
        try:
            os.mkdir(dir)
        except OSError:
            print(f"\nCreazione della cartella {dir} fallita...")

    origin_stdout = sys.stdout

    origin_stderr = sys.stderr

    sys.stdout = open(os.path.join(dir, f"{index}.txt"), "w")

    sys.stderr = open(os.path.join(dir, f"{index}.txt"), "w")

    traci.start(sumoCmd, port=port, numRetries=1000)

    """Inizializzazione di alcune variabili"""

    vehicles = {}  # dizionario contente dei riferimenti ad oggetto: idVx: Vehicle(x)
    totalTime = 0  # tempo totale di simulazione
    counter_serving = {}  # dizionario contenente valori incrementali
    counter_served = {}  # dizionario contenente valori incrementali
    serving = {}  # dizionario dei throughput misurati per ogni lane entrante per ogni step
    served = {}  # dizionario dei throughput misurati per ogni lane uscente per ogni step
    headTimes = []  # lista dei tempi passati in testa per ogni veicolo
    varHeadTime = 0  # varianza rispetto al tempo passato in testa
    tailTimes = []  # lista dei tempi in coda per ogni veicolo
    varTailTime = 0  # varianza rispetto al tempo passato in coda
    meanSpeeds = []  # medie delle velocità assunte dai veicoli ad ogni step
    varSpeed = 0  # varianza rispetto alla velocità dei veicoli
    nStoppedVehicles = []  # lista che dice se i veicoli si sono fermati all'incrocio o no
    meanTailLength = []  # medie delle lunghezze delle code rilevate sulle lane entranti ad ogni step
    varTail = 0  # varianza rispetto alla coda
    maxTail = -1  # coda massima rilevata su tutte le lane entranti
    tails_per_lane = {}  # dizionario contenente le lunghezze delle code per ogni lane ad ogni step
    junction_shape = traci.junction.getShape("n" + str(junction_id))

    for lane in lanes:
        # calcolo la lunghezza delle code e il throughput solo per le lane entranti
        if lane[4:6] == '07':
            tails_per_lane[lane] = []
            serving[lane] = []
            served[lane] = []
            counter_serving[lane] = 0
            counter_served[lane] = 0

    """Con il seguente ciclo inizializzo i veicoli assegnadogli una route legale generata casualmente e, in caso di 
    schema di colori non significativo,dandogli un colore diverso per distinguerli meglio all'interno della 
    simulazione"""

    for i in range(0, numberOfVehicles):
        idV = f"idV{i}"
        # oggetto veicolo:
        # headStopTime: considera il tempo passato in testa (con un piccolo delay dovuto alla ripartenza del veicolo)
        # followerStopTime: considera il tempo passato in coda
        # speeds: lista con i valori delle velocità assunte in ogni step
        # stopped: variabile che indica che il veicolo si è fermato all'incrocio
        vehicle = {'id': idV, 'headStopTime': 0, 'followerStopTime': 0, 'speeds': [], 'hasStopped': 0, 'hasEntered': 0,
                   'isCrossing': 0, 'hasCrossed': 0, 'startingLane': ''}
        vehicles[idV] = Vehicle(idV, vehicle, instantPay)
        start = random.choice(node_ids)
        end = random.choice([x for x in node_ids if x != start])
        lane = getLaneFromEdges(node_ids, start, end)
        traci.route.add(f'route_{i}', [f'e{"0" if start != 12 else ""}{start}_0{junction_id}',
                                       f'e0{junction_id}_{"0" if end != 12 else ""}{end}'])
        traci.vehicle.add(idV, f'route_{i}', departLane=lane)
        if schema in ['n', 'N']:
            if i % 8 == 1:
                traci.vehicle.setColor(f'idV{i}', (0, 255, 255))  # azzurro
            if i % 8 == 2:
                traci.vehicle.setColor(f'idV{i}', (160, 100, 100))  # rosa
            if i % 8 == 3:
                traci.vehicle.setColor(f'idV{i}', (255, 0, 0))  # rosso
            if i % 8 == 4:
                traci.vehicle.setColor(f'idV{i}', (0, 255, 0))  # verde
            if i % 8 == 5:
                traci.vehicle.setColor(f'idV{i}', (0, 0, 255))  # blu
            if i % 8 == 6:
                traci.vehicle.setColor(f'idV{i}', (255, 255, 255))  # bianco
            if i % 8 == 7:
                traci.vehicle.setColor(f'idV{i}', (255, 0, 255))  # viola
            if i % 8 == 8:
                traci.vehicle.setColor(f'idV{i}', (255, 100, 0))  # arancione

    """Di seguito inizializzo l'incrocio che fa parte della simulazione, assegnandogli una classe che ne descriva
    il comportamento specifico"""

    junction = FourWayJunction(junction_id, vehicles, iP=instantPay, sM=simulationMode, bM=False,
                               groupDimension=dimensionOfGroups)

    """Di seguito il ciclo entro cui avviene tutta la simulazione, una volta usciti la simulazione è conclusa"""

    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        totalTime += 1

        """Ciclo principale dell'applicazione"""

        """Prime operazioni sull'incrocio"""

        vehAtJunction = junction.getVehiclesAtJunction()
        crossingManager = junction.getCrossingManager()
        crossingManager.updateCrossingStatus(vehicles)

        """Flusso principale"""

        for idVeh in vehAtJunction:
            if idVeh in vehicles:
                objVeh = vehicles[idVeh]

                if objVeh.distanceFromEndLane() < 50:
                    if objVeh not in crossingManager.getCurrentPartecipants():
                        crossingManager.updateVehicleStatus(objVeh)
                    # se non è gia in una auction, non e stoppato
                    if objVeh.distanceFromEndLane() < 15:
                        if objVeh in crossingManager.getCrossingStatus().values() and objVeh not in \
                                crossingManager.getVehiclesInAuction() and objVeh.checkPosition(junction) \
                                and objVeh not in crossingManager.nonStoppedVehicles:
                            junction.createAuction(objVeh, vehicles)

        if len(vehAtJunction) > 0:
            crossingManager.allowCrossing()

        vehs_loaded = traci.vehicle.getIDList()
        for lane in tails_per_lane:
            tails_per_lane[lane].append(0)
            if totalTime % period == 0:
                serving[lane].append(counter_serving[lane])
                served[lane].append(counter_served[lane])
                counter_serving[lane] -= counter_served[lane]
                counter_served[lane] = 0
        # loop per tutti i veicoli
        for veh in vehs_loaded:
            veh_current_lane = traci.vehicle.getLaneID(veh)
            # controllo se il veicolo è nella junction
            if veh_current_lane[1:3] == 'n7':
                vehicles[veh].measures['speeds'].append(traci.vehicle.getSpeed(veh))
                vehicles[veh].measures['hasEntered'] = 0
                vehicles[veh].measures['isCrossing'] = 1
                if schema in ['s', 'S']:
                    traci.vehicle.setColor(veh, (255, 255, 0))  # giallo
            # controllo se il veicolo è in una lane uscente
            if veh_current_lane[1:3] == '07':
                vehicles[veh].measures['isCrossing'] = 0
                if vehicles[veh].measures['hasCrossed'] == 0:
                    counter_served[vehicles[veh].measures['startingLane']] += 1
                    vehicles[veh].measures['hasCrossed'] = 1
                if schema in ['s', 'S']:
                    traci.vehicle.setColor(veh, (0, 255, 0))  # verde
            # controllo se il veicolo è in una lane entrante
            if veh_current_lane[4:6] == '07':
                vehicles[veh].measures['startingLane'] = veh_current_lane
                spawn_distance = traci.vehicle.getDistance(veh)
                distance = getDistanceFromLaneEnd(spawn_distance, traci.lane.getLength(veh_current_lane),
                                                  junction_shape)
                if distance < 15:
                    vehicles[veh].measures['speeds'].append(traci.vehicle.getSpeed(veh))
                veh_length = traci.vehicle.getLength(veh)
                check = veh_length / 2 + 0.2
                leader = traci.vehicle.getLeader(veh)
                if vehicles[veh].measures['hasEntered'] == 0:
                    counter_serving[veh_current_lane] += 1
                    vehicles[veh].measures['hasEntered'] = 1
                if traci.vehicle.getSpeed(veh) <= 1:
                    # verifico se il veicolo si è fermato al di fuori del punto di spawn
                    if spawn_distance > 0:
                        vehicles[veh].measures['hasStopped'] = 1
                        tails_per_lane[veh_current_lane][totalTime - 1] += 1
                    # verifico se il veicolo è in testa
                    if check >= distance and ((leader and leader[1] > 0.5) or not leader):
                        vehicles[veh].measures['headStopTime'] += 1
                        if schema in ['s', 'S']:
                            traci.vehicle.setColor(veh, (0, 0, 255))  # blu
                        continue
                    # verifico se il veicolo è in coda
                    if leader and leader[1] <= 0.5 and vehicles[leader[0]].measures['startingLane'] == veh_current_lane:
                        vehicles[veh].measures['followerStopTime'] += 1
                        if schema in ['s', 'S']:
                            traci.vehicle.setColor(veh, (255, 0, 0))  # rosso
                        continue
                else:
                    if schema in ['s', 'S']:
                        traci.vehicle.setColor(veh, (255, 255, 0))  # giallo

    if totalTime % period != 0:
        for lane in tails_per_lane:
            serving[lane].append(counter_serving[lane])
            served[lane].append(counter_served[lane])

    """Salvo tutti i risultati della simulazione e li ritorno"""

    for veh in vehicles:
        headTimes.append(vehicles[veh].measures['headStopTime'])
        tailTimes.append(vehicles[veh].measures['followerStopTime'])
        meanSpeeds.append(sum(vehicles[veh].measures['speeds']) / len(vehicles[veh].measures['speeds']))
        nStoppedVehicles.append(vehicles[veh].measures['hasStopped'])

    meanHeadTime = sum(headTimes) / len(headTimes)
    for headTime in headTimes:
        varHeadTime += (headTime - meanHeadTime) ** 2
    varHeadTime /= len(headTimes)

    meanTailTime = sum(tailTimes) / len(tailTimes)
    for tailTime in tailTimes:
        varTailTime += (tailTime - meanTailTime) ** 2
    varTailTime /= len(tailTimes)

    meanSpeed = sum(meanSpeeds) / len(meanSpeeds)
    for speed in meanSpeeds:
        varSpeed += (speed - meanSpeed) ** 2
    varSpeed /= len(meanSpeeds)

    for lane in tails_per_lane:
        meanTailLength.append(sum(tails_per_lane[lane]) / len(tails_per_lane[lane]))
        lane_max = max(tails_per_lane[lane])
        if lane_max > maxTail:
            maxTail = lane_max

    meanTail = sum(meanTailLength) / len(meanTailLength)
    for tail in meanTailLength:
        varTail += (tail - meanTail) ** 2
    varTail /= len(meanTailLength)

    instant_throughput = {}
    for lane in serving:
        instant_throughput[lane] = []

    mean_served = {}
    for lane in serving:
        for i in range(0, len(serving[lane])):
            if serving[lane][i] == 0:
                instant_throughput[lane].append(1)
            else:
                instant_throughput[lane].append(served[lane][i] / serving[lane][i])
        mean_served[lane] = sum(instant_throughput[lane]) / len(instant_throughput[lane])

    meanTP = sum([mean_served[lane] for lane in mean_served]) / len([mean_served[lane] for lane in mean_served])

    traci.close()

    sys.stdout = origin_stdout

    sys.stderr = origin_stderr

    queue.put([totalTime, meanHeadTime, sqrt(varHeadTime), max(headTimes), meanTailTime, sqrt(varTailTime),
               max(tailTimes), meanSpeed, sqrt(varSpeed), meanTail, sqrt(varTail), maxTail, sum(nStoppedVehicles),
               meanTP])