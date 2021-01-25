import sys
import os
import random
from math import sqrt
import matplotlib.pyplot as plt
import numpy as np

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Dichiarare la variabile d'ambiente 'SUMO_HOME'")

from sumolib import checkBinary  # noqa
import traci  # noqa

config_file = "intersection.sumocfg"  # file di configurazione della simulazione
junction_id = 7  # id dell'incrocio
lanes = []  # lista dei nomi delle lane
lanes_ids = [0, 2, 4]  # lista degli id delle lanes nell'incrocio
node_ids = [2, 8, 12, 6]  # lista degli id dei nodi di partenza e di arrivo nell'incrocio
period = 10  # tempo di valutazione del throughput del sistema incrocio
num_measures = 15  # numero di misure effettuate nella simulazione

"""Con questo ciclo inizializzo i nomi delle lane così come sspecificate nel file intersection.net.xml"""
for i in node_ids:
    for lane in lanes_ids:
        lanes.append(f'e{"0" if i < 12 else ""}{i}_0{junction_id}_{lane}')
        lanes.append(f'e0{junction_id}_{"0" if i < 12 else ""}{i}_{lane}')


def get_lane_from_edges(node_ids, start, end):
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


def run(numberOfVehicles, schema, sumoCmd):
    """Funzione che avvia la simulazione dato un certo numero di veicoli"""

    traci.start(sumoCmd, numRetries=50)
    vehicles = {}  # dizionario contente gli id dei veicoli
    totalTime = 0  # tempo totale di simulazione
    counter_serving = {}  # dizionario contenente valori incrementali
    counter_served = {}  # dizionario contenente valori incrementali
    serving = {}  # dizionario dei throughput misurati per ogni lane entrante per ogni step
    served = {}  # dizionario dei throughput misurati per ogni lane uscente per ogni step
    meanTPPerLane = []  # medie delle lunghezze delle code rilevate sulle lane entranti ad ogni step
    headTimes = []  # lista dei tempi passati in testa per ogni veicolo
    varHeadTime = 0  # varianza rispetto al tempo passato in testa
    tailTimes = []  # lista dei tempi in coda per ogni veicolo
    varTailTime = 0  # varianza rispetto al tempo passato in coda
    meanSpeeds = []  # medie delle velocità assunte dai veicoli ad ogni step
    maxSpeed = -1  # velocità massima rilevata su tutti i veicoli
    nStoppedVehicles = []  # lista che dice se i veicoli si sono fermati all'incrocio o no
    meanTailLength = []  # medie delle lunghezze delle code rilevate sulle lane entranti ad ogni step
    tails_per_lane = {}  # dizionario contenente le lunghezze delle code per ogni lane ad ogni step
    maxTail = -1  # coda massima rilevata su tutte le lane entranti
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
    for n in range(1, numberOfVehicles + 1):
        idV = str(n)
        # oggetto veicolo:
        # headStopTime: considera il tempo passato in testa (con un piccolo delay dovuto alla ripartenza del veicolo)
        # followerStopTime: considera il tempo passato in coda
        # speeds: lista con i valori delle velocità assunte in ogni step
        # stopped: variabile che indica che il veicolo si è fermato all'incrocio
        vehicle = {'id': idV, 'headStopTime': 0, 'followerStopTime': 0, 'speeds': [], 'hasStopped': 0, 'hasEntered': 0,
                   'isCrossing': 0, 'hasCrossed': 0, 'startingLane': ''}
        vehicles[idV] = vehicle
        start = random.choice(node_ids)
        end = random.choice([x for x in node_ids if x != start])
        lane = get_lane_from_edges(node_ids, start, end)
        traci.route.add(f'route_{n}', [f'e{"0" if start != 12 else ""}{start}_0{junction_id}',
                                       f'e0{junction_id}_{"0" if end != 12 else ""}{end}'])
        traci.vehicle.add(idV, f'route_{n}', departLane=lane)
        if schema in ['n', 'N']:
            if n % 8 == 1:
                traci.vehicle.setColor(f'{n}', (0, 255, 255))  # azzurro
            if n % 8 == 2:
                traci.vehicle.setColor(f'{n}', (160, 100, 100))  # rosa
            if n % 8 == 3:
                traci.vehicle.setColor(f'{n}', (255, 0, 0))  # rosso
            if n % 8 == 4:
                traci.vehicle.setColor(f'{n}', (0, 255, 0))  # verde
            if n % 8 == 5:
                traci.vehicle.setColor(f'{n}', (0, 0, 255))  # blu
            if n % 8 == 6:
                traci.vehicle.setColor(f'{n}', (255, 255, 255))  # bianco
            if n % 8 == 7:
                traci.vehicle.setColor(f'{n}', (255, 0, 255))  # viola
            if n % 8 == 8:
                traci.vehicle.setColor(f'{n}', (255, 100, 0))  # arancione

    """Di seguito il ciclo entro cui avviene tutta la simulazione, una volta usciti la simulazione è conclusa."""
    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        totalTime += 1
        vehs_loaded = traci.vehicle.getIDList()
        for lane in tails_per_lane:
            tails_per_lane[lane].append(0)
            if totalTime % period == 0:
                serving[lane].append(counter_serving[lane])
                served[lane].append(counter_served[lane])
                counter_serving[lane] -= counter_served[lane]
                if counter_serving[lane] < 0:
                    print(f"Ecco!!!, problema: {counter_serving[lane] - counter_served[lane]}")
                counter_served[lane] = 0
        # loop per tutti i veicoli
        for veh in vehs_loaded:
            veh_current_lane = traci.vehicle.getLaneID(veh)
            # controllo se il veicolo è nella junction
            if veh_current_lane[1:3] == 'n7':
                vehicles[veh]['hasEntered'] = 0
                vehicles[veh]['isCrossing'] = 1
                leader = traci.vehicle.getLeader(veh)
                leader_lane = ''
                if leader:
                    leader_lane = traci.vehicle.getLaneID(leader[0])
                if traci.vehicle.getSpeed(veh) <= 1:
                    tails_per_lane[vehicles[veh]['startingLane']][totalTime - 1] += 1
                    # verifico se il veicolo è in testa
                    if (leader and leader_lane != veh_current_lane) or not leader:
                        vehicles[veh]['headStopTime'] += 1
                        if schema in ['s', 'S']:
                            traci.vehicle.setColor(veh, (0, 0, 255))  # blu
                        continue
                    # verifico se il veicolo è in coda
                    if leader and leader[1] <= 0.5 and leader and leader_lane == veh_current_lane:
                        vehicles[veh]['followerStopTime'] += 1
                        if schema in ['s', 'S']:
                            traci.vehicle.setColor(veh, (255, 0, 0))  # rosso
                        continue
                else:
                    if schema in ['s', 'S']:
                        traci.vehicle.setColor(veh, (255, 255, 0))  # giallo
            # controllo se il veicolo è in una lane uscente
            if veh_current_lane[1:3] == '07':
                vehicles[veh]['isCrossing'] = 0
                if vehicles[veh]['hasCrossed'] == 0:
                    print(f"Veicolo {veh} è stato servito")
                    counter_served[vehicles[veh]['startingLane']] += 1
                    vehicles[veh]['hasCrossed'] = 1
                if schema in ['s', 'S']:
                    traci.vehicle.setColor(veh, (0, 255, 0))  # verde
            # controllo se il veicolo è in una lane entrante
            if veh_current_lane[4:6] == '07':
                vehicles[veh]['startingLane'] = veh_current_lane
                vehicles[veh]['speeds'].append(traci.vehicle.getSpeed(veh))
                distance = traci.vehicle.getNextTLS(veh)[0][2]
                veh_length = traci.vehicle.getLength(veh)
                check = veh_length / 2 + 0.2
                leader = traci.vehicle.getLeader(veh)
                spawn_distance = traci.vehicle.getDistance(veh)
                if vehicles[veh]['hasEntered'] == 0:
                    print(f"Veicolo {veh} deve essere servito")
                    counter_serving[veh_current_lane] += 1
                    vehicles[veh]['hasEntered'] = 1
                if traci.vehicle.getSpeed(veh) <= 1:
                    # verifico se il veicolo si è fermato al di fuori del punto di spawn
                    if spawn_distance > 0:
                        vehicles[veh]['hasStopped'] = 1
                        tails_per_lane[veh_current_lane][totalTime - 1] += 1
                    # verifico se il veicolo è in testa
                    if check >= distance and ((leader and leader[1] > 0.5) or not leader):
                        vehicles[veh]['headStopTime'] += 1
                        if schema in ['s', 'S']:
                            traci.vehicle.setColor(veh, (0, 0, 255))  # blu
                        continue
                    # verifico se il veicolo è in coda
                    if leader and leader[1] <= 0.5:
                        vehicles[veh]['followerStopTime'] += 1
                        if schema in ['s', 'S']:
                            traci.vehicle.setColor(veh, (255, 0, 0))  # rosso
                        continue
    if totalTime % period != 0:
        for lane in tails_per_lane:
                serving[lane].append(counter_serving[lane])
                served[lane].append(counter_served[lane])

    """Salvo tutti i risultati della simulazione e li ritorno."""
    for veh in vehicles:
        headTimes.append(vehicles[veh]['headStopTime'])
        tailTimes.append(vehicles[veh]['followerStopTime'])
        meanSpeeds.append(sum(vehicles[veh]['speeds']) / len(vehicles[veh]['speeds']))
        speed_max = max(vehicles[veh]['speeds'])
        if speed_max > maxSpeed:
            maxSpeed = speed_max
        nStoppedVehicles.append(vehicles[veh]['hasStopped'])

    meanHeadTime = sum(headTimes) / len(headTimes)
    for headTime in headTimes:
        varHeadTime += (headTime - meanHeadTime) ** 2
    varHeadTime /= len(headTimes)

    meanTailTime = sum(tailTimes) / len(tailTimes)
    for tailTime in tailTimes:
        varTailTime += (tailTime - meanTailTime) ** 2
    varTailTime /= len(tailTimes)

    for lane in tails_per_lane:
        meanTailLength.append(sum(tails_per_lane[lane]) / len(tails_per_lane[lane]))
        lane_max = max(tails_per_lane[lane])
        if lane_max > maxTail:
            maxTail = lane_max

    instant_throughput = {}
    for lane in serving:
        instant_throughput[lane] = []
    mean_served = {}
    for lane in serving:
        print(f"Serving: {serving[lane]}, Served: {served[lane]}, Lane: {lane}")
        for i in range(0, len(serving[lane])):
            if serving[lane][i] == 0:
                instant_throughput[lane].append(1)
            else:
                instant_throughput[lane].append(served[lane][i] / serving[lane][i])
        mean_served[lane] = sum(instant_throughput[lane]) / len(instant_throughput[lane])
    meanTP = sum([mean_served[lane] for lane in mean_served]) / len([mean_served[lane] for lane in mean_served])

    traci.close()

    return totalTime, meanHeadTime, varHeadTime, max(headTimes), meanTailTime, varTailTime, \
           max(tailTimes), sum(meanSpeeds) / len(meanSpeeds), maxSpeed, sum(meanTailLength) / len(meanTailLength), \
           maxTail, sum(nStoppedVehicles), meanTP


def checkInput(d, def_string, ask_string, error_string):
    """Funzione che verifica se l'input dell'utente è corretto"""

    i = 0
    while i <= 0:
        t = input(def_string)
        if t == '':
            i = d  # default
            print(ask_string)
        else:
            try:
                i = int(t)
            except:
                print(error_string)
                i = 0
                continue
            if i <= 0:
                print(error_string)
    return i


if __name__ == "__main__":
    """Main che avvia un certo numero di simulazioni in serie"""

    choice = ''
    schema = 'n'
    labels_per_sims = []
    while choice not in ['d', 'D', 'g', 'G']:
        choice = input('\nVuoi raccogliere dati o avere una visualizzazione grafica? (d = dati, g = grafica): ')
        if choice not in ['d', 'D', 'g', 'G']:
            print('\nInserire un carattere tra d e g!')
    if choice in ['d', 'D']:
        sumoBinary = checkBinary('sumo')
        sumoCmd = [sumoBinary, "-c", config_file, "--time-to-teleport", "-1"]
    else:
        sumoBinary = checkBinary('sumo-gui')
        sumoCmd = [sumoBinary, "-c", config_file, "--time-to-teleport", "-1"]
        choice = ''
        while choice not in ['s', 'S', 'n', 'N']:
            choice = input('\nDesideri visualizzare le auto con uno schema di colori significativo? (s, n): ')
            if choice not in ['s', 'S', 'n', 'N']:
                print('\nInserire un carattere tra s e n!')
        schema = choice
    numberOfSimulations = checkInput(1, '\nInserire il numero di simulazioni: ',
                                     f'\nUtilizzo una simulazione come default...',
                                     '\nInserire un numero di simulazioni positivo!')
    f = open("output_no_batch.txt", "w")
    hists_per_sims = []
    for i in range(0, num_measures):
        hists_per_sims.append([])
    for i in range(1, numberOfSimulations + 1):
        numberOfVehicles = checkInput(50, f'\nInserire il numero di veicoli nella simulazione {i}: ',
                                      f'\nUtilizzo la simulazione {i} con 50 veicoli di default...',
                                      '\nInserire un numero di veicoli positivo!')
        labels_per_sims.append(f'Sim. {i} ({numberOfVehicles} veicoli)')
        totalTime, meanHeadTime, varHeadTime, maxHeadTime, meanTailTime, varTailTime, maxTailTime, meanSpeed, maxSpeed, \
        meanTailLength, maxTailLength, nStoppedVehicles, meanThroughput = run(numberOfVehicles, schema, sumoCmd)
        f.write('----------------------------------------------------\n')
        f.write(f'\nSIMULAZIONE NUMERO {i}\n')
        f.write('\n----------------------------------------------------\n')
        f.write(f'\nNUMERO DI VEICOLI: {numberOfVehicles}\n')
        f.write(f'\nTEMPO TOTALE DI SIMULAZIONE: {totalTime} step\n')
        f.write(f'\nTEMPO MEDIO PASSATO IN TESTA A UNA CORSIA: {round(meanHeadTime, 2)} step\n')
        f.write(f'\nVARIANZA DEL TEMPO PASSATO IN TESTA A UNA CORSIA: {round(varHeadTime, 2)} step\n')
        f.write(
            f'\nDEVIAZIONE STANDARD DEL TEMPO PASSATO IN TESTA A UNA CORSIA: {round(sqrt(varHeadTime), 2)} step\n')
        f.write(f'\nTEMPO MASSIMO PASSATO IN TESTA A UNA CORSIA: {maxHeadTime} step\n')
        f.write(f'\nTEMPO MEDIO PASSATO IN CODA: {round(meanTailTime, 2)} step\n')
        f.write(f'\nVARIANZA DEL TEMPO PASSATO IN CODA A UNA CORSIA: {round(varTailTime, 2)} step\n')
        f.write(
            f'\nDEVIAZIONE STANDARD DEL TEMPO PASSATO IN CODA A UNA CORSIA: {round(sqrt(varTailTime), 2)} step\n')
        f.write(f'\nTEMPO MASSIMO PASSATO IN CODA: {maxTailTime} step\n')
        f.write(f'\nVELOCITA MEDIA DEI VEICOLI: {round(meanSpeed, 2)} m/s\n')
        f.write(f'\nVELOCITA MASSIMA DEI VEICOLI: {round(maxSpeed, 2)} m/s\n')
        f.write(f'\nLUNGHEZZA MEDIA DELLE CODE: {round(meanTailLength, 2)} auto\n')
        f.write(f'\nLUNGHEZZA MASSIMA DELLE CODE: {round(maxTailLength, 2)} auto\n')
        f.write(
            f'\nNUMERO DI VEICOLI FERMI: {nStoppedVehicles} ({round(nStoppedVehicles / numberOfVehicles * 100, 2)}%)\n')
        f.write(f'\nTHROUGHPUT MEDIO: {round(meanThroughput, 2)}\n\n')
        hists_per_sims[0].append(round(totalTime, 2))
        hists_per_sims[1].append(round(meanHeadTime, 2))
        hists_per_sims[2].append(round(varHeadTime, 2))
        hists_per_sims[3].append(round(sqrt(varHeadTime), 2))
        hists_per_sims[4].append(round(maxHeadTime, 2))
        hists_per_sims[5].append(round(meanTailTime, 2))
        hists_per_sims[6].append(round(varTailTime, 2))
        hists_per_sims[7].append(round(sqrt(varTailTime), 2))
        hists_per_sims[8].append(round(maxTailTime, 2))
        hists_per_sims[9].append(round(meanSpeed, 2))
        hists_per_sims[10].append(round(maxSpeed, 2))
        hists_per_sims[11].append(round(meanTailLength, 2))
        hists_per_sims[12].append(round(maxTailTime, 2))
        hists_per_sims[13].append(round(nStoppedVehicles, 2))
        hists_per_sims[14].append(round(meanThroughput, 2))
    f.close()

    """Mostro a schermo l'istogramma con le misure medie per ogni simulazione"""
    r = np.arange(len(hists_per_sims[0]))
    width = 0.01
    fig, ax = plt.subplots()
    rect1 = ax.bar(r - 7 * width, hists_per_sims[0], width, color='#FF5733', label='Tempo totale (s)')
    rect2 = ax.bar(r - 6 * width, hists_per_sims[1], width, color='#FFF933', label='Tempo medio in testa (s)')
    rect3 = ax.bar(r - 5 * width, hists_per_sims[2], width, color='#9FFF33', label='Varianza tempo in testa (s)')
    rect4 = ax.bar(r - 4 * width, hists_per_sims[3], width, color='#33FF3C', label='Deviazione standard tempo in '
                                                                                   'testa (s)')
    rect5 = ax.bar(r - 3 * width, hists_per_sims[4], width, color='#33FFC7', label='Tempo massimo in testa (s)')
    rect6 = ax.bar(r - 2 * width, hists_per_sims[5], width, color='#33A5FF', label='Tempo medio in coda (s)')
    rect7 = ax.bar(r - width, hists_per_sims[6], width, color='#3340FF', label='Varianza tempo in coda (s)')
    rect8 = ax.bar(r, hists_per_sims[7], width, color='#9B33FF', label='Deviazione standard tempo in coda (s)')
    rect9 = ax.bar(r + width, hists_per_sims[8], width, color='#E633FF', label='Tempo massimo in coda (s)')
    rect10 = ax.bar(r + 2 * width, hists_per_sims[9], width, color='#FF33B3', label='Velocità media (m/s)')
    rect11 = ax.bar(r + 3 * width, hists_per_sims[10], width, color='#FF334D', label='Velocità massima (m/s)')
    rect12 = ax.bar(r + 4 * width, hists_per_sims[11], width, color='#486246', label='Lunghezza media delle code')
    rect13 = ax.bar(r + 5 * width, hists_per_sims[12], width, color='#1E6153', label='Lunghezza massima delle code')
    rect14 = ax.bar(r + 6 * width, hists_per_sims[13], width, color='#D0D1E6', label='Numero di veicoli fermi')
    ax.set_title('Valori medi delle simulazioni effettuate')
    ax.set_xticks(r)
    ax.set_xticklabels(labels_per_sims)
    lgd = ax.legend(title='Legenda', bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    plt.savefig('results_no_batch.png', bbox_inches='tight')

    """Mostro il grafico del throughput separato per via di valori molto piccoli"""
    r = np.arange(len(hists_per_sims[14]))
    width = 0.05
    fig_tp, ax = plt.subplots()
    rect15 = ax.bar(r, hists_per_sims[14], width, color='#FF5733', label=f'Throughput medio (veicoli / {period} step)')
    ax.set_xticks(r)
    ax.set_xticklabels(labels_per_sims)
    lgd_tp = ax.legend(title='Legenda', bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    plt.savefig('throughput_no_batch.png', bbox_inches='tight')