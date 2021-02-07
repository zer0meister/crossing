import sys
import os
import random
import math
from math import sqrt
import output
from multiprocessing import Queue
import trafficElements.auction
from trafficElements.competitive import CompetitiveCrossingManager
from reservation_auction.trafficElements.auction import CompetitiveAuction

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Dichiarare la variabile d'ambiente 'SUMO_HOME'")

from sumolib import checkBinary, miscutils  # noqa
import traci  # noqa
from reservation.traiettorie import Traiettorie

config_file = "intersection.sumocfg"  # file di configurazione della simulazione
junction_id = 7  # id dell'incrocio
lanes = []  # lista dei nomi delle lane
lanes_ids = [0, 2, 4]  # lista degli id delle lanes nell'incrocio
node_ids = [2, 8, 12, 6]  # lista degli id dei nodi di partenza e di arrivo nell'incrocio
period = 10  # tempo di valutazione del throughput del sistema
partecipants = []
precedences = {}
partecipantsRoutes = {}
vehiclesInAuction = []
currentWinners = []
currentLosers = []
winnersLanes = {}

"""Con questo ciclo inizializzo i nomi delle lane così come sspecificate nel file intersection.net.xml"""
for i in node_ids:
    for lane in lanes_ids:
        lanes.append(f'e{"0" if i < 12 else ""}{i}_0{junction_id}_{lane}')
        lanes.append(f'e0{junction_id}_{"0" if i < 12 else ""}{i}_{lane}')


def getIndexFromEdges(node_ids, start, end):
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
    # print(f"Shape: {shape}\n")
    for point in shape:
        if point[0] < min_x:
            min_x = point[0]
        if point[0] > max_x:
            max_x = point[0]
    # print(f"Max x: {max_x}, Min x: {min_x}, Lane length: {lane_length}\n")
    lane_end = lane_length - (max_x - min_x) / 2
    # print(f"Lane end = lane_length - (max_x - min_x) / 2 = {lane_end}\n")
    # print(f"Distance: {lane_end - spawn_distance}")
    return lane_end - spawn_distance


def generateRoute(node_ids, junction_id):
    """Genero tutte le route possibili per l'incrocio"""

    n = 0

    for i in node_ids:
        for j in node_ids:
            if i == j:
                continue
            start = i
            end = j
            traci.route.add(f'route_{n}', [f'e{"0" if start != 12 else ""}{start}_0{junction_id}',
                                           f'e0{junction_id}_{"0" if end != 12 else ""}{end}'])
            n += 1


def generaVeicoli(n_auto_t, t_gen, vehicles):
    """Genero veicoli per ogni route"""

    r_depart = 0
    auto_ogni = float(t_gen) / float(n_auto_t)

    generateRoute(node_ids, junction_id)

    for i in range(0, n_auto_t):
        r_depart += auto_ogni
        idV = str(i)
        vehicle = {'id': idV, 'headStopTime': 0, 'followerStopTime': 0, 'speeds': [], 'hasStopped': 0, 'hasEntered': 0,
                   'isCrossing': 0, 'hasCrossed': 0, 'startingLane': ''}
        vehicles[idV] = vehicle
        r = int(random.randint(0, 11))
        edges = traci.route.getEdges(f'route_{r}')
        lane = getIndexFromEdges(node_ids, int(edges[0][1:3]), int(edges[1][4:6]))
        id_veh = str(i)
        traci.vehicle.add(id_veh, f'route_{r}', departLane=lane)
        traci.vehicle.setParameter(id_veh, "wallet", random.randint(10, 100))

    return vehicles


def stopXY(shape_temp):
    """Calcolo estremi dell'incrocio, dove sono presenti gli stop"""

    stop_temp = []

    for count in range(0, len(shape_temp) - 1):
        if shape_temp[count][0] == shape_temp[count + 1][0]:
            stop_temp.append(shape_temp[count][0])
        elif shape_temp[count][1] == shape_temp[count + 1][1]:
            stop_temp.append(shape_temp[count][1])

    return stop_temp


def limiti_celle(estremi_incrocio, celle_per_lato):
    """Calcolo i metri all'interno dell'incrocio di ogni cella della matrice"""

    # definisco i vettori
    limiti_celle_X_temp = []
    limiti_celle_Y_temp = []

    # lunghezza totale incrocio nell'asse X e Y
    lunghezza_X = estremi_incrocio[1] - estremi_incrocio[3]
    lunghezza_Y = estremi_incrocio[0] - estremi_incrocio[2]

    # lunghezza di una sola cella
    lungh_cella_X = float(lunghezza_X) / float(celle_per_lato)
    lungh_cella_Y = float(lunghezza_Y) / float(celle_per_lato)

    for i in range(0, celle_per_lato + 1):  # scrivo sui vettori
        limiti_celle_X_temp.append(round((estremi_incrocio[3] + (lungh_cella_X * i)), 3))
        limiti_celle_Y_temp.append(round((estremi_incrocio[0] - (lungh_cella_Y * i)), 3))

    return [limiti_celle_X_temp, limiti_celle_Y_temp]


def get_cella_from_pos_auto(auto_temp, limiti_celle_X_temp, limiti_celle_Y_temp):
    """Ritorno le coordinate della cella nella matrice in cui si trova l'auto"""

    cella_X = 0
    cella_Y = 0
    pos = traci.vehicle.getPosition(auto_temp)

    for x in range(0, len(limiti_celle_X_temp) - 1):
        if limiti_celle_X_temp[x] <= pos[0] <= limiti_celle_X_temp[x + 1]:
            cella_X = x

    for y in range(0, len(limiti_celle_Y_temp) - 1):
        if limiti_celle_Y_temp[y] >= pos[1] >= limiti_celle_Y_temp[y + 1]:
            cella_Y = y

    return [auto_temp, cella_X, cella_Y]


def in_incrocio(pos_temp, estremi_incrocio):
    """Controllo se l'auto è all'incrocio"""

    if (estremi_incrocio[3] <= pos_temp[0] <= estremi_incrocio[1]) and \
            (estremi_incrocio[2] <= pos_temp[1] <= estremi_incrocio[0]):
        return True
    else:
        return False


def metri_da_incrocio(auto_temp, estremi_incrocio):
    """Calcolo la distanza dell'auto in metri dall'incrocio come numero negativo (l'inizio dell'incrocio è 0)"""

    pos = traci.vehicle.getPosition(auto_temp)
    ang = traci.vehicle.getAngle(auto_temp)
    dist = 0
    if ang == 0:
        dist = abs(float(estremi_incrocio[2]) - float(pos[1]))
    if ang == 180:
        dist = abs(float(estremi_incrocio[0]) - float(pos[1]))
    if ang == 90:
        dist = abs(float(estremi_incrocio[3]) - float(pos[0]))
    if ang == 270:
        dist = abs(float(estremi_incrocio[1]) - float(pos[0]))
    dist = 0 - dist
    return dist


def t_arrivo_cella(auto_temp, metri_da_incrocio_temp, metri_da_cella_temp):
    """Calcolo il timestep di arrivo sulla cella"""

    vi = traci.vehicle.getSpeed(auto_temp)
    vf = traci.vehicle.getMaxSpeed(auto_temp)
    a = traci.vehicle.getAccel(auto_temp)
    xa = (((vf * vf) - (vi * vi)) / (float(2) * a)) + metri_da_incrocio_temp
    t1 = (- vi + math.sqrt((vi * vi) + (float(2) * a) * (xa - metri_da_incrocio_temp))) / a
    t2 = (metri_da_cella_temp - xa) / vf
    t = t1 + t2
    t = round(t, 4)

    return t + traci.simulation.getTime()


def celle_occupate_data_ang(ang, x_auto_in_celle_temp, y_auto_in_celle_temp):
    """Restituisce le celle occupate data l'angolazione del veicolo, centrate in [0][0]"""

    celle_occupate = []
    ang = ang % 180
    ang = - ang
    x_auto = x_auto_in_celle_temp * 1.2
    y_auto = y_auto_in_celle_temp * 1.1

    ang = math.radians(ang)  # converto in radianti
    a1 = [- float(x_auto) / float(2), float(y_auto) / float(2)]
    a2 = [float(x_auto) / float(2), float(y_auto) / float(2)]
    b1 = [- float(x_auto) / float(2), - float(y_auto) / float(2)]
    b2 = [float(x_auto) / float(2), - float(y_auto) / float(2)]

    # coordinate degli angoli ruotati
    a1 = [round(a1[0] * math.cos(ang) - a1[1] * math.sin(ang), 4),
          round(a1[0] * math.sin(ang) + a1[1] * math.cos(ang), 4)]
    a2 = [round(a2[0] * math.cos(ang) - a2[1] * math.sin(ang), 4),
          round(a2[0] * math.sin(ang) + a2[1] * math.cos(ang), 4)]
    b1 = [round(b1[0] * math.cos(ang) - b1[1] * math.sin(ang), 4),
          round(b1[0] * math.sin(ang) + b1[1] * math.cos(ang), 4)]
    b2 = [round(b2[0] * math.cos(ang) - b2[1] * math.sin(ang), 4),
          round(b2[0] * math.sin(ang) + b2[1] * math.cos(ang), 4)]

    r1 = [a2[1] - a1[1], a1[0] - a2[0], - a1[0] * a2[1] + a2[0] * a1[1]]
    r2 = [b2[1] - a2[1], a2[0] - b2[0], - a2[0] * b2[1] + b2[0] * a2[1]]
    r3 = [b2[1] - b1[1], b1[0] - b2[0], - b1[0] * b2[1] + b2[0] * b1[1]]
    r4 = [b1[1] - a1[1], a1[0] - b1[0], - a1[0] * b1[1] + b1[0] * a1[1]]

    # per ogni cella guardo se uno dei 4 angoli e' all'interno del rettangolo
    massimo = max([x_auto, y_auto])
    for y_cella in range(-int(massimo / 2) - 3, int(massimo / 2) + 4):
        for x_cella in range(-int(massimo / 2) - 3, int(massimo / 2) + 4):
            inserito = False
            if not inserito and (r1[0] * (x_cella - 0.5) + r1[1] * (y_cella - 0.5) + r1[2] >= 0) and \
                    (r2[0] * (x_cella - 0.5) + r2[1] * (y_cella - 0.5) + r2[2] >= 0) and \
                    (r3[0] * (x_cella - 0.5) + r3[1] * (y_cella - 0.5) + r3[2] <= 0) and \
                    (r4[0] * (x_cella - 0.5) + r4[1] * (y_cella - 0.5) + r4[2] <= 0):
                celle_occupate.append([y_cella, x_cella])
                inserito = True
            if not inserito and (r1[0] * (x_cella + 0.5) + r1[1] * (y_cella - 0.5) + r1[2] >= 0) and \
                    (r2[0] * (x_cella + 0.5) + r2[1] * (y_cella - 0.5) + r2[2] >= 0) and \
                    (r3[0] * (x_cella + 0.5) + r3[1] * (y_cella - 0.5) + r3[2] <= 0) and \
                    (r4[0] * (x_cella + 0.5) + r4[1] * (y_cella - 0.5) + r4[2] <= 0):
                celle_occupate.append([y_cella, x_cella])
                inserito = True
            if not inserito and (r1[0] * (x_cella - 0.5) + r1[1] * (y_cella + 0.5) + r1[2] >= 0) and \
                    (r2[0] * (x_cella - 0.5) + r2[1] * (y_cella + 0.5) + r2[2] >= 0) and \
                    (r3[0] * (x_cella - 0.5) + r3[1] * (y_cella + 0.5) + r3[2] <= 0) and \
                    (r4[0] * (x_cella - 0.5) + r4[1] * (y_cella + 0.5) + r4[2] <= 0):
                celle_occupate.append([y_cella, x_cella])
                inserito = True
            if not inserito and (r1[0] * (x_cella + 0.5) + r1[1] * (y_cella + 0.5) + r1[2] >= 0) and \
                    (r2[0] * (x_cella + 0.5) + r2[1] * (y_cella + 0.5) + r2[2] >= 0) and \
                    (r3[0] * (x_cella + 0.5) + r3[1] * (y_cella + 0.5) + r3[2] <= 0) and \
                    (r4[0] * (x_cella + 0.5) + r4[1] * (y_cella + 0.5) + r4[2] <= 0):
                celle_occupate.append([y_cella, x_cella])
                inserito = True

    return celle_occupate


def arrivoAuto(auto_temp, passaggio_temp, ferme_temp, attesa_temp, matrice_incrocio_temp, passaggio_cella_temp,
               traiettorie_matrice_temp, estremi_incrocio, sec_sicurezza, x_auto_in_celle_temp, y_auto_in_celle_temp):
    """Gestisco l'arrivo dell'auto in prossimità dello stop"""

    if not get_from_matrice_incrocio(auto_temp, matrice_incrocio_temp, traiettorie_matrice_temp, estremi_incrocio,
                                     sec_sicurezza, x_auto_in_celle_temp, y_auto_in_celle_temp):
        # faccio fermare l'auto
        ferme_temp.append(auto_temp)
        traci.vehicle.setSpeed(auto_temp, 0.0)
    # l'auto può passare, la segno nella matrice e nei vettori
    else:
        traci.vehicle.setSpeedMode(auto_temp, 30)
        passaggio_temp.append([auto_temp, traci.vehicle.getRoadID(auto_temp), traci.vehicle.getAngle(auto_temp)])
        # tolgo l'auto dalla lista d'attesa e la sottoscrivo nella matrice
        attesa_temp.pop(attesa_temp.index(auto_temp))
        matrice_incrocio_temp = set_in_matrice_incrocio(auto_temp, matrice_incrocio_temp, traiettorie_matrice_temp,
                                                        estremi_incrocio, x_auto_in_celle_temp, y_auto_in_celle_temp)

        rotta = traci.vehicle.getRouteID(auto_temp)
        edges = traci.route.getEdges(rotta)
        lane = getIndexFromEdges(node_ids, int(edges[0][1:3]), int(edges[1][4:6]))
        # se l'auto non gira a destra
        if lane != 0:
            passaggio_cella_temp.append([auto_temp, None, None])
        # se l'auto gira a destra la faccio rallentare fino a dimezzarne la velocità
        else:
            traci.vehicle.setSpeed(auto_temp, traci.vehicle.getMaxSpeed(auto_temp) / float(2))

    ritorno = [passaggio_temp, attesa_temp, ferme_temp, matrice_incrocio_temp, passaggio_cella_temp]
    return ritorno


def set_in_matrice_incrocio(auto_temp, matrice_incrocio_temp, traiettorie_matrice_temp, estremi_incrocio,
                            x_auto_in_celle_temp, y_auto_in_celle_temp):
    """Segna sulla matrice_incrocio l'occupazione delle celle toccate dall'auto durante l'attraversamento"""

    rotta = traci.vehicle.getRouteID(auto_temp)

    for route in traiettorie_matrice_temp:
        if route[0] == rotta:
            for celle in route[1]:
                # calcolo timestep di arrivo su tale cella
                timestep = t_arrivo_cella(auto_temp, metri_da_incrocio(auto_temp, estremi_incrocio), celle[2])
                celle_occupate = celle_occupate_data_ang(celle[3], x_auto_in_celle_temp, y_auto_in_celle_temp)
                # controllo le celle occupate dall'auto
                for celle_circostanti in celle_occupate:
                    index_y = celle_circostanti[0]
                    index_x = celle_circostanti[1]
                    if ((celle[0] + index_y) >= 0) and ((celle[1] + index_x) >= 0) and \
                            ((celle[0] + index_y) < len(matrice_incrocio_temp)) and \
                            ((celle[1] + index_x) < len(matrice_incrocio_temp)):
                        matrice_incrocio_temp[celle[0] + index_y][celle[1] + index_x].append(round(timestep, 4))

    return matrice_incrocio_temp


def get_from_matrice_incrocio(auto_temp, matrice_incrocio_temp, traiettorie_matrice_temp, estremi_incrocio,
                              sec_sicurezza, x_auto_in_celle_temp, y_auto_in_celle_temp):
    """Data l'auto e la matrice dell'incrocio restituisce True se non sono state rilevate collisioni
    dall'attuale situazione di passaggio rilevata all'interno della matrice, False se sono rilevate collisioni"""

    rotta = traci.vehicle.getRouteID(auto_temp)

    libero = True

    for route in traiettorie_matrice_temp:
        if route[0] == rotta and libero:
            for celle in route[1]:
                timestep = t_arrivo_cella(auto_temp, metri_da_incrocio(auto_temp, estremi_incrocio), celle[2])
                celle_occupate = celle_occupate_data_ang(celle[3], x_auto_in_celle_temp, y_auto_in_celle_temp)
                # controllo le celle occupate dall'auto
                for celle_circostanti in celle_occupate:
                    index_y = celle_circostanti[0]
                    index_x = celle_circostanti[1]
                    if ((celle[0] + index_y) >= 0) and ((celle[1] + index_x) >= 0) and \
                            ((celle[0] + index_y) < len(matrice_incrocio_temp)) and \
                            ((celle[1] + index_x) < len(matrice_incrocio_temp)):
                        # scorre i tempi di occupazione segnati all'interno della cella
                        for t in matrice_incrocio_temp[celle[0] + index_y][celle[1] + index_x]:
                            # controlla che il timestep di arrivo calcolato non cada in un range di sicurezza
                            # dal valore selezionato
                            if t - sec_sicurezza <= timestep <= t + sec_sicurezza:
                                libero = False
                                break

    return libero


def percorso_libero(passaggio_temp, matrice_incrocio_temp, passaggio_cella_temp, limiti_celle_X_temp,
                    limiti_celle_Y_temp,
                    estremi_incrocio):
    """Controllo se è cambiata la situazione all'interno dell'incrocio"""

    passaggio_nuovo = passaggio_temp[:]
    passaggio_cella_nuovo = passaggio_cella_temp[:]

    for x in passaggio_temp:

        rotta = traci.vehicle.getRouteID(x[0])
        edges = traci.route.getEdges(rotta)
        lane = getIndexFromEdges(node_ids, int(edges[0][1:3]), int(edges[1][4:6]))
        # se l'auto non gira a destra
        if lane != 0:
            for y in passaggio_cella_temp:
                if x[0] == y[0]:

                    pos = traci.vehicle.getPosition(x[0])
                    # se l'auto è ancora nell'incrocio
                    if in_incrocio(pos, estremi_incrocio):

                        cella = get_cella_from_pos_auto(x[0], limiti_celle_X_temp, limiti_celle_Y_temp)
                        pos_attuale_X = cella[1]
                        pos_attuale_Y = cella[2]
                        # se la posizione dell'auto nelle celle cambia
                        if pos_attuale_X != y[1] or pos_attuale_Y != y[2]:
                            # aggiorno poi il vettore con la nuova posizione della cella in cui si trova l'auto
                            passaggio_cella_nuovo[passaggio_cella_nuovo.index(y)] = [y[0], pos_attuale_X, pos_attuale_Y]
                    # se l'auto è uscita dall'incrocio
                    else:
                        # se ho None allora l'auto non è ancora entrata nell'incrocio e non la tolgo
                        if y[1] is not None and y[2] is not None:
                            passaggio_nuovo.pop(passaggio_nuovo.index(x))
                            passaggio_cella_nuovo.pop(passaggio_cella_nuovo.index(y))
        # se gira a destra guardo se cambia strada e la tolgo dal vettore passaggio
        else:
            road = prossimaStrada(x)
            if traci.vehicle.getRoadID(x[0]) == road:
                passaggio_nuovo.pop(passaggio_nuovo.index(x))
                # faccio riaccelerare l'auto
                traci.vehicle.setSpeed(x[0], traci.vehicle.getMaxSpeed(x[0]) * 4)

    info = [passaggio_nuovo, matrice_incrocio_temp, passaggio_cella_nuovo]
    return info


def avantiAuto(auto_temp, passaggio_temp, attesa_temp, ferme_temp, matrice_incrocio_temp, passaggio_cella_temp,
               traiettorie_matrice_temp, estremi_incrocio, x_auto_in_celle_temp, y_auto_in_celle_temp):
    """Faccio avanzare le auto"""

    traci.vehicle.setSpeedMode(auto_temp, 30)

    traci.vehicle.setSpeed(auto_temp, traci.vehicle.getMaxSpeed(auto_temp))  # riparte l'auto
    passaggio_temp.append([auto_temp, traci.vehicle.getRoadID(auto_temp), traci.vehicle.getAngle(auto_temp)])
    matrice_incrocio_temp = set_in_matrice_incrocio(auto_temp, matrice_incrocio_temp, traiettorie_matrice_temp,
                                                    estremi_incrocio, x_auto_in_celle_temp, y_auto_in_celle_temp)

    if ferme_temp:
        try:
            ferme_temp.pop(ferme_temp.index(auto_temp))  # tolgo dalla lista di auto ferme
        except ValueError:  # per le auto che faccio partire senza fermare non serve toglerle dalla lista
            pass
    attesa_temp.pop(attesa_temp.index(auto_temp))  # tolgo dalla lista l'auto
    passaggio_cella_temp.append([auto_temp, None, None])
    info = [passaggio_temp, attesa_temp, ferme_temp, matrice_incrocio_temp, passaggio_cella_temp]
    return info


def prossimaStrada(passaggio_temp):
    """Ottengo il nome della via a cui l'auto e' diretta"""

    route = traci.vehicle.getRoute(passaggio_temp[0])  # ottengo rotta dell'auto che sta attraversando
    att_road = passaggio_temp[1]  # strada attuale
    pross_roadID = route.index(att_road) + 1  # posizione nel vettore attuale via + 1 = prossima
    pross_road = route[pross_roadID]  # prossima strada
    return pross_road


def costruzioneArray(arrayAuto_temp):
    """Costruzione dell'array composto dal nome delle auto presenti nella simulazione"""

    loadedIDList = traci.simulation.getDepartedIDList()  # carica nell'array le auto partite
    for id_auto in loadedIDList:
        if id_auto not in arrayAuto_temp:
            arrayAuto_temp.append(id_auto)
            traci.vehicle.setSpeed(id_auto, traci.vehicle.getMaxSpeed(id_auto))

    arrivedIDList = traci.simulation.getArrivedIDList()  # elimina nell'array le auto arrivate
    for id_auto in arrivedIDList:
        if id_auto in arrayAuto_temp:
            arrayAuto_temp.pop(arrayAuto_temp.index(id_auto))

    return arrayAuto_temp


def pulisci_matrice(matrice_incrocio_temp, sec_sicurezza_temp):
    "Ogni 10 step pulisco la matrice da valori vecchi"

    matrice_incrocio = []
    for incr in matrice_incrocio_temp:
        index_incr = matrice_incrocio_temp.index(incr)
        matrice_incrocio.append(incr)
        for y in matrice_incrocio_temp[index_incr]:
            index_y = matrice_incrocio_temp[index_incr].index(y)
            for x in matrice_incrocio_temp[index_incr][index_y]:
                index_x = matrice_incrocio_temp[index_incr][index_y].index(x)
                for val in matrice_incrocio_temp[index_incr][index_y][index_x]:
                    index_val = matrice_incrocio_temp[index_incr][index_y][index_x].index(val)
                    if val < (traci.simulation.getTime() - sec_sicurezza_temp - 1):
                        matrice_incrocio[index_incr][index_y][index_x].pop(index_val)

    return matrice_incrocio


def getDistanceFromLaneEnd(spawn_distance, lane_length, shape):
    """Calcolo la distanza tra il veicolo e l'inizio dell'incrocio"""

    min_x = shape[0][0]
    max_x = shape[0][0]
    # print(f"Shape: {shape}\n")
    for point in shape:
        if point[0] < min_x:
            min_x = point[0]
        if point[0] > max_x:
            max_x = point[0]
    # print(f"Max x: {max_x}, Min x: {min_x}, Lane length: {lane_length}\n")
    lane_end = lane_length - (max_x - min_x) / 2
    # print(f"Lane end = lane_length - (max_x - min_x) / 2 = {lane_end}\n")
    # print(f"Distance: {lane_end - spawn_distance}")
    return lane_end - spawn_distance


def getNonStoppedVehicles(vehicles):
    return [x for x in vehicles if vehicles[x]["hasStopped"] != 1]


def getCrossingStatus(vehicles):
    crossingStatus = {}
    for lane in lanes:
        crossingStatus[lane].append(traci.lane.getLastStepVehicleIDs(lane))
    return crossingStatus


def getLanesFromEdges(node_ids, start, end):
    """Funzione che trova la lane corretta da far seguire al veicolo dati il nodo di partenza e quello di
    destinazione"""

    s = start[1:3]
    e = end[1:3]

    distance = -1
    i = 0
    trovato = False
    while True:
        if node_ids[i % 4] == s:
            trovato = True
        if trovato:
            distance += 1
            if node_ids[i % 4] == e:
                break
        i += 1
    lane = 0
    if distance == 1:
        lane = 4
    if distance == 2:
        lane = 2
    if distance == 3:
        lane = 0
    return start + f"_{str(lane)}", end + f"_{str(lane)}"


def findClashingRoutesWhenGoForward(junction_id, left, front, right, base):
    """Funzione altamente specifica per la rete utilizzata che memorizza le traiettorie incidentali interne
    all'incrocio, in particolare quelle che si hanno nell'andare diritto."""
    clashingEdges = []
    clashingEdge1 = (f'e{"0" if right < 10 else ""}{right}_{"0" if junction_id < 10 else ""}{junction_id}_2',
                     f'e{"0" if junction_id < 10 else ""}{junction_id}_{"0" if left < 10 else ""}{left}_2')
    clashingEdges.append(clashingEdge1)
    clashingEdge2 = (f'e{"0" if right < 10 else ""}{right}_{"0" if junction_id < 10 else ""}{junction_id}_4',
                     f'e{"0" if junction_id < 10 else ""}{junction_id}_{base[1:3]}_4')
    clashingEdges.append(clashingEdge2)
    clashingEdge3 = (f'e{"0" if left < 10 else ""}{left}_{"0" if junction_id < 10 else ""}{junction_id}_2',
                     f'e{"0" if junction_id < 10 else ""}{junction_id}_{"0" if right < 10 else ""}{right}_2')
    clashingEdges.append(clashingEdge3)
    clashingEdge4 = (f'e{"0" if front < 10 else ""}{front}_{"0" if junction_id < 10 else ""}{junction_id}_4',
                     f'e{"0" if junction_id < 10 else ""}{junction_id}_{"0" if right < 10 else ""}{right}_4')
    clashingEdges.append(clashingEdge4)
    return clashingEdges


def findClashingRoutesWhenTurningLeft(junction_id, left, front, right, base):
    """Funzione altamente specifica per la rete utilizzata che memorizza le traiettorie incidentali interne
    all'incrocio, in particolare quelle che si hanno nello svoltare a sinistra."""
    clashingEdges = []
    clashingEdge1 = (f'e{"0" if right < 10 else ""}{right}_{"0" if junction_id < 10 else ""}{junction_id}_4',
                     f'e{"0" if junction_id < 10 else ""}{junction_id}_{base[1:3]}_4')
    clashingEdges.append(clashingEdge1)
    clashingEdge2 = (f'e{"0" if left < 10 else ""}{left}_{"0" if junction_id < 10 else ""}{junction_id}_2',
                     f'e{"0" if junction_id < 10 else ""}{junction_id}_{"0" if right < 10 else ""}{right}_2')
    clashingEdges.append(clashingEdge2)
    clashingEdge3 = (f'e{"0" if left < 10 else ""}{left}_{"0" if junction_id < 10 else ""}{junction_id}_4',
                     f'e{"0" if junction_id < 10 else ""}{junction_id}_{"0" if front < 10 else ""}{front}_4')
    clashingEdges.append(clashingEdge3)
    clashingEdge4 = (f'e{"0" if front < 10 else ""}{front}_{"0" if junction_id < 10 else ""}{junction_id}_2',
                     f'e{"0" if junction_id < 10 else ""}{junction_id}_{base[1:3]}_2')
    clashingEdges.append(clashingEdge4)
    return clashingEdges


def getArrivalEdgesFromEdge(start):
    """Funzione che trova la lane corretta da far seguire al veicolo dati il nodo di partenza e quello di
    destinazione"""

    distance = -1
    i = 0
    edges = []
    trovato = False
    while True:
        if node_ids[i % 4] == start:
            trovato = True
        if trovato:
            distance += 1
            edges.append(node_ids[(i + 1) % 4])
            if distance == 3:
                break
        i += 1
    return edges[0], edges[1], edges[2]


def isClashing(route1, route2):
    """funzione che prende in ingresso 2 coppie del tipo: lane attuale e lane obbiettivo, ritornando True se le
    route sono in collisione, False altrimenti"""
    left, front, right = getArrivalEdgesFromEdge(route1[0])
    index = getIndexFromEdges(node_ids, int(route1[0][1:3]), int(route1[1][1:3]))
    r2 = ("", "")
    r2[0], r2[1] = getLanesFromEdges(node_ids, route2[0], route2[1])
    if index == 2:
        if r2 in findClashingRoutesWhenGoForward(junction_id, left, front, right, route1[0]):
            return True
    if index == 4:
        if r2 in findClashingRoutesWhenTurningLeft(junction_id, left, front, right, route1[0]):
            return True
    return False


def addWinner(vehicle):
    """Funzione che aggiunge il vincitore sia ai veicoli vincitori sia a quelli in un'asta"""
    currentWinners.append(vehicle)
    vehiclesInAuction.append(vehicle)
    assert currentWinners.count(vehicle) == 1, vehicle
    assert vehiclesInAuction.count(vehicle) == 1, vehicle


def removeWinner(vehicle):
    """Funzione che rimuove un veicolo vincitore dalla lista dei vincitori e dei partecipanti ad un'asta"""
    currentWinners.remove(vehicle)
    vehiclesInAuction.remove(vehicle)
    assert currentWinners.count(vehicle) == 0, vehicle
    assert vehiclesInAuction.count(vehicle) == 0, vehicle


def addLoser(vehicle):
    """Funzione che aggiunge il vincitore sia ai veicoli sconfitti sia a quelli in un'asta"""
    currentLosers.append(vehicle)
    vehiclesInAuction.append(vehicle)
    assert currentLosers.count(vehicle) == 1, vehicle
    assert vehiclesInAuction.count(vehicle) == 1, vehicle


def removeLoser(vehicle):
    """Funzione che rimuove un veicolo vincitore dalla lista degli sconfitti e dei partecipanti ad un'asta"""
    currentLosers.remove(vehicle)
    vehiclesInAuction.remove(vehicle)
    assert currentLosers.count(vehicle) == 0, vehicle
    assert vehiclesInAuction.count(vehicle) == 0, vehicle


def saveAuctionResults(auction):
    """Funzione utilizzata per salvare i risultati di un'asta nel caso di non bufferizzazione e quindi di non
    necessità di un merge dei vincitori. Evita di utilizzare la struttura delle precedenze, in modo da risparmiare
    complessità computazionale."""
    winners = auction.getWinners()
    losers = auction.getLosers()
    winnersLanes[winners[0].getCurrentLane()] = winners
    # print(f'BBB {[v.getID() for v in winners]}')
    for i in winners:
        if i not in partecipants:
            partecipants.append(i)
            if not i.isStopped():
                i.stopVehicle()
            # print('saving', i.getID(), 'sar', self.junction.getID(), 'w', i.distanceFromEndLane())
            partecipantsRoutes[i] = getLanesFromEdges(node_ids, traci.vehicle.getRoute(i)[0],
                                                      traci.vehicle.getRoute(i)[1])
        if i in currentLosers:
            removeLoser(i)
        addWinner(i)
        precedences[i] = losers
    #     print(f'precedences of veh {i.getID()}: {[j.getID() for j in self.precedences[i]]}')
    # print([i.getID() for i in self.getCurrentWinners()], 'junction', self.junction.getID())
    for i in losers:
        addLoser(i)
        partecipantsRoutes[i] = getLanesFromEdges(node_ids, traci.vehicle.getRoute(i)[0], traci.vehicle.getRoute(i)[1])
        i.nVehiclesToWait += len(winners)
        if i not in partecipants:
            partecipants.append(i)
            if not i.isStopped():
                i.stopVehicle()
            precedences[i] = []
            # print('saving', i.getID(), 'sar', self.junction.getID(), 'l', i.distanceFromEndLane())

    # print('saving auction result of', self.junction.getID())


def createAuction(idVeh, vehicles):
        """Funzione che permette di aggiungere un'asta all'elenco di quelle attualmente in corso nell'incrocio
           :param idVeh: ID del veicolo di cui si cercheranno i rivali.
           :param vehicles: veicoli raggruppati per corsia d'appartenenza;"""

        """Ramo importante della funzione."""
        lp = []
        ls = []
        """Se è variabile otterrò una dimensione dipendente dal numero di veicoli in corsia."""
        maxLength = 12  # non importante, ritorna maxNumberOfVehicles
        """Ciclo sulla reversed del getLastStepVehicleIDs() per selezionare prima i veicoli più vicini 
        all'incrocio."""
        for veh in reversed(traci.lane.getLastStepVehicleIDs(idVeh.getCurrentLane())):
            spawn_distance = traci.vehicle.getDistance(veh)
            lane_length = traci.lane.getLength(traci.vehicle.getLaneID(veh))
            shape = traci.junction.getShape("n" + str(junction_id))
            veh = vehicles[veh]
            # print(f'conditions on {veh.getID()} ({veh.getCurrentLane()}): posizione {veh.checkPosition(self)}, '
            # f'auction {veh not in self.crossingManager.vehiclesInAuction}, veicoli riattivati {veh not in self.crossingManager.nonStoppedVehicles}, '
            # f'distanza {veh.distanceFromEndLane() < 40}, maxLength {len(lp) < maxLength}')
            # se veicolo non e tra quelli in auction ed è stoppato
            if veh not in vehiclesInAuction \
                    and veh not in getNonStoppedVehicles(vehicles):
                if getDistanceFromLaneEnd(spawn_distance, lane_length, shape) < 40 and len(lp) < maxLength:
                    lp.append(veh)
                    # print(f'adding {veh.getID()} to lp')
                else:
                    ls.append(veh)
                    # print(f'adding {veh.getID()} to ls')

        clashingLists = [[lp, ls]]
        vv = [[[[x.getID()] for x in l] for l in group] for group in clashingLists]

        # print(f'clashingLists: {vv}')
        clashingVehicles = [idVeh]
        vv = [v.getID() for v in clashingVehicles]
        # print(f'clashingVehicles: {vv}')
        vehiclesInHead = []
        for i in getCrossingStatus(vehicles).values():
            spawn_distance = traci.vehicle.getDistance(i)
            lane_length = traci.lane.getLength(traci.vehicle.getLaneID(i))
            shape = traci.junction.getShape("n" + str(junction_id))
            if i is not None and i not in vehiclesInAuction and \
                i not in getNonStoppedVehicles(vehicles) \
                and getDistanceFromLaneEnd(spawn_distance, lane_length, shape) < 15:
                vehiclesInHead.append(i)
        vv = [v.getID() for v in vehiclesInHead]
        # print(f'vehiclesInHead: {vv}')

        """Cerco i veicoli in traiettoria incidentale con quelli pronti a partecipare all'asta."""
        for veh in clashingVehicles:
            # print('veh subject', veh.getID(), veh.getCurrentRoute())
            # print(f'subject {veh.getID()} ({veh.getCurrentLane()})')
            for otherVeh in vehiclesInHead:
                # print(f'object {otherVeh.getID()} ({otherVeh.getCurrentLane()}), condizioni: diversità {otherVeh != veh}, non presenza '
                # f'{otherVeh not in clashingVehicles}, clashing {self.isClashing(self.fromEdgesToLanes(veh), self.fromEdgesToLanes(otherVeh))}')
                if otherVeh != veh and otherVeh not in clashingVehicles:
                    lanes_veh = getLanesFromEdges(node_ids, traci.vehicle.getRoute(veh)[0], traci.vehicle.getRoute(veh)[1])
                    lanes_other_veh = getLanesFromEdges(node_ids, traci.vehicle.getRoute(otherVeh)[0], traci.vehicle.getRoute(otherVeh[1]))
                    if isClashing(lanes_veh, lanes_other_veh):
                        clashingVehicles.append(otherVeh)
                        vlp = []
                        vls = []
                        maxLength = 12
                        for v in reversed(traci.lane.getLastStepVehicleIDs(otherVeh.getCurrentLane())):
                            v = vehicles[v]
                            # print(
                            #     f'conditions on {v.getID()} ({v.getCurrentLane()}): posizione {v.checkPosition(self)}, '
                            #     f'auction {v not in self.crossingManager.vehiclesInAuction}, veicoli riattivati {v not in self.crossingManager.nonStoppedVehicles}, '
                            #     f'distanza {v.distanceFromEndLane() < 40}, maxLength {len(vlp) < maxLength}')
                            if v not in vehiclesInAuction \
                                    and v not in getNonStoppedVehicles(vehicles):
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
                        lanes_veh = getLanesFromEdges(node_ids, traci.vehicle.getRoute(veh)[0],
                                                      traci.vehicle.getRoute(veh)[1])
                        lanes_other_veh = getLanesFromEdges(node_ids, traci.vehicle.getRoute(bv)[0],
                                                            traci.vehicle.getRoute(bv[1]))
                        if isClashing(lanes_veh, lanes_other_veh):
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

        if len(clashingLists) > 1:
            auction = CompetitiveAuction(clashingLists, junction_id, False, True, False)
            saveAuctionResults(auction)


def run(numberOfVehicles, schema, sumoCmd, tempo_generazione, celle_per_lato, traiettorie_matrice,
        secondi_di_sicurezza, path, index, queue):
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

    traci.start(sumoCmd, port=port)

    vehicles = {}  # dizionario contente gli id dei veicoli
    step = 0.000  # tempo totale di simulazione
    step_incr = 0.025  # incremento del numero di step della simulazione
    sec = 1 / step_incr
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
    maxSpeed = -1  # velocità massima rilevata su tutti i veicoli
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

    generaVeicoli(numberOfVehicles, tempo_generazione, vehicles)

    """Con il seguente ciclo inizializzo i veicoli assegnadogli una route legale generata casualmente e, in caso di 
    schema di colori non significativo,dandogli un colore diverso per distinguerli meglio all'interno della 
    simulazione"""
    for n in range(0, numberOfVehicles):
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

    # istanzio le matrici [nome_incrocio, variabile]
    attesa = []  # ordine di arrivo su lista, si resetta quando le auto liberano incrocio
    passaggio = []  # auto in passaggio nell'incrocio
    lista_arrivo = []  # auto entrate nelle vicinanze dell'incrocio, non si resetta
    matrice_incrocio = []  # rappresenta la suddivisione matriciale dell'incrocio (in celle)
    lista_uscita = []  # auto uscite dall'incrocio, non si resetta
    ferme = []  # lista di auto ferme allo stop
    stop = []  # lista che indica di quanto si distanzia lo stop dal centro dell'incrocio [dx, sotto, sx, sopra]
    centerJunctID = []  # coordinate (x,y) del centro di un incrocio
    arrayAuto = []  # contiene la lista di auto presenti nella simulazione
    tempo_coda = []  # usata per fare calcoli su output del tempo medio in coda
    limiti_celle_X = []  # utile per verificare l'appartenenza ad una cella all'interno della matrice dell'incrocio
    limiti_celle_Y = []  # utile per verificare l'appartenenza ad una cella all'interno della matrice dell'incrocio
    passaggio_cella = []  # salvo in che cella si trova l'auto in passaggio [incrID][ [ auto , cella_X , cella_Y ],... ]
    consumo = dict()  # lista di consumi rilevati per ogni auto
    rallentate = []  # lista di auto rallentate in prossimità dell'incrocio
    passaggio_precedente = []  # salvo l'ultima situazione di auto in passaggio per rilasciarle all'uscita

    f_s = []
    vm_s = []
    cm_s = []
    cx_s = []

    attesa.append([])
    lista_arrivo.append([])
    lista_uscita.append([])
    ferme.append([])
    passaggio.append([])
    rallentate.append([])
    passaggio_cella.append([])
    passaggio_precedente.append([])

    centerJunctID.append(traci.junction.getPosition('n' + str(junction_id)))  # posizione del centro dell'incrocio

    shape = traci.junction.getShape('n' + str(junction_id))  # forma dell'incrocio
    stop.append(stopXY(shape))  # estremi dell'incrocio, dove sono presenti gli stop

    # popolo i vettori limiti_celle_X e limiti_celle_Y
    limiti = limiti_celle(stopXY(shape), celle_per_lato)
    limiti_celle_X.append(limiti[0])
    limiti_celle_Y.append(limiti[1])
    # popolo il vettore per il calcolo del tempo medio in coda
    tempo_coda.append([])
    for i in range(0, numberOfVehicles):
        tempo_coda[0].insert(i, [0, 0])
    # popolo la matrice dell'incrocio
    matrice_incrocio.append([])
    for x in range(0, celle_per_lato):
        matrice_incrocio[0].append([])
        for y in range(0, celle_per_lato):
            # ogni cella è un'array dei tempi stimati di occupazione della medesima
            matrice_incrocio[0][x].append([])
    # inserisco nell'array le auto presenti nella simulazione
    arrayAuto = costruzioneArray(arrayAuto)

    # trovo lunghezza e altezza auto in celle
    x_cella_in_m = abs(limiti_celle_X[0][1] - limiti_celle_X[0][0])
    y_cella_in_m = abs(limiti_celle_Y[0][1] - limiti_celle_Y[0][0])
    x_auto_in_m = traci.vehicle.getHeight("0")
    y_auto_in_m = traci.vehicle.getLength("0")
    x_auto_in_celle = float(x_auto_in_m) / float(x_cella_in_m)
    y_auto_in_celle = float(y_auto_in_m) / float(y_cella_in_m)
    # fino a quando tutte le auto da inserire hanno terminato la corsa

    n_step = 0

    while traci.simulation.getMinExpectedNumber() > 0:
        incrID = 0

        for auto in arrayAuto:  # scorro l'array delle auto ancora presenti nella simulazione

            auto_in_lista = True
            # vedo se l'auto corrente è tra le auto segnate per attraversare l'incrocio
            try:
                presente = int(lista_arrivo[incrID].index(auto))
            except ValueError:
                auto_in_lista = False
            pos = traci.vehicle.getPosition(auto)
            # se l'auto non è in lista allora guardo se sta entrando nelle vicinanze dell'incrocio
            if not auto_in_lista:
                stop_temp = stop[incrID]

                if (stop_temp[3] - 50 <= pos[0] <= stop_temp[1] + 50) and \
                        (stop_temp[2] - 50 <= pos[1] <= stop_temp[0] + 50):
                    # inserisco l'auto nella lista d'arrivo di quell'incrocio
                    lista_arrivo[incrID].append(auto)
                    # inserisco l'auto nella lista d'attesa di quell'incrocio
                    attesa[incrID].append(auto)
                    traci.vehicle.setMaxSpeed(auto, 6.944444)
            # se l'auto è in attesa e non è ferma, guardo se è vicina allo stop e fermo se l'incrocio è già occupato
            if auto in attesa[incrID] and auto not in ferme[incrID]:
                # se l'incrocio ha 4 lati
                if len(stop_temp) > 3:
                    if (stop_temp[3] - 13.5 <= pos[0] <= stop_temp[1] + 13.5) and \
                            (stop_temp[2] - 13.5 <= pos[1] <= stop_temp[0] + 13.5):
                        traci.vehicle.setDecel(auto, 1.92901)
                        traci.vehicle.setAccel(auto, 1.92901)
                        # salvo l'auto leader di quella lane
                        leader = traci.vehicle.getLeader(auto)
                        if leader:
                            # se il leader ha già iniziato ad attraversare l'incrocio non lo conto
                            if leader[0] not in attesa[incrID]:
                                leader = None
                        # se non c'è il leader su quella lane
                        if not leader:
                            # controllo se l'auto non ha subito rallentamenti e la fermo in 16 m
                            if round(traci.vehicle.getSpeed(auto), 2) == round(traci.vehicle.getMaxSpeed(auto), 2):
                                info = arrivoAuto(auto, passaggio[incrID], ferme[incrID], attesa[incrID],
                                                  matrice_incrocio[incrID], passaggio_cella[incrID],
                                                  traiettorie_matrice, stop[incrID], secondi_di_sicurezza,
                                                  x_auto_in_celle, y_auto_in_celle)
                                passaggio[incrID] = info[0]
                                attesa[incrID] = info[1]
                                ferme[incrID] = info[2]
                                matrice_incrocio[incrID] = info[3]
                                passaggio_cella[incrID] = info[4]
                            # se l'auto ha subito rallentamenti calcolo dalla sua velocità in quanti metri
                            # dall'incrocio si fermerebbe se la facessi rallentare subito, se si va a fermare in
                            # prossimità dell'incrocio allora avvio l'arresto del veicolo altrimenti aspetto
                            # il prossimo step e ricontrollo
                            else:
                                dist_stop = 0
                                v_auto = traci.vehicle.getSpeed(auto)
                                decel = traci.vehicle.getDecel(auto)

                                ang = traci.vehicle.getAngle(auto)

                                if ang == 90:
                                    dist_stop = abs(stop_temp[3] - pos[0])
                                if ang == 0:
                                    dist_stop = abs(stop_temp[2] - pos[1])
                                if ang == 270:
                                    dist_stop = abs(stop_temp[1] - pos[0])
                                if ang == 180:
                                    dist_stop = abs(stop_temp[0] - pos[1])

                                dist_to_stop = (v_auto * v_auto) / (2 * decel)

                                if dist_to_stop + 2 >= dist_stop:
                                    info = arrivoAuto(auto, passaggio[incrID], ferme[incrID], attesa[incrID],
                                                      matrice_incrocio[incrID], passaggio_cella[incrID],
                                                      traiettorie_matrice, stop[incrID], secondi_di_sicurezza,
                                                      x_auto_in_celle, y_auto_in_celle)
                                    passaggio[incrID] = info[0]
                                    attesa[incrID] = info[1]
                                    ferme[incrID] = info[2]
                                    matrice_incrocio[incrID] = info[3]
                                    passaggio_cella[incrID] = info[4]
        # se ci sono auto che stanno attraversando l'incrocio guardo se la situazione dell'incrocio è cambiata
        if passaggio[incrID] is not None:
            # se l'auto è appena entrata nell'area dell'incrocio salvo la cella in cui si trova
            for x in passaggio_cella[incrID]:
                rotta = traci.vehicle.getRouteID(x[0])
                edges = traci.route.getEdges(rotta)
                lane = getIndexFromEdges(node_ids, int(edges[0][1:3]), int(edges[1][4:6]))
                if lane != 0:
                    # se l'auto non gira a destra
                    if x[1] is None and x[2] is None:
                        pos = traci.vehicle.getPosition(x[0])
                        if in_incrocio(pos, stop[incrID]):
                            IDvett = passaggio_cella[incrID].index(x)
                            passaggio_cella[incrID][IDvett] = get_cella_from_pos_auto(x[0], limiti_celle_X[incrID],
                                                                                      limiti_celle_Y[incrID])

            info = percorso_libero(passaggio[incrID], matrice_incrocio[incrID], passaggio_cella[incrID],
                                   limiti_celle_X[incrID], limiti_celle_Y[incrID], stop[incrID])
            passaggio[incrID] = info[0]
            matrice_incrocio[incrID] = info[1]
            passaggio_cella[incrID] = info[2]
            # se ci sono auto ferme, vedo se posso farne partire qualcuna
            if len(ferme[incrID]) > 0:

                # scorro tra tutte le auto ferme e se una è compatibile con la matrice allora la faccio partire
                for auto_ferma in ferme[incrID]:
                    if auto_ferma in ferme[incrID]:
                        if get_from_matrice_incrocio(auto_ferma, matrice_incrocio[incrID], traiettorie_matrice,
                                                     stop[incrID], secondi_di_sicurezza, x_auto_in_celle,
                                                     y_auto_in_celle):
                            # vedo se il suo percorso è libero e nel caso la faccio partire
                            info = avantiAuto(auto_ferma, passaggio[incrID], attesa[incrID], ferme[incrID],
                                              matrice_incrocio[incrID], passaggio_cella[incrID],
                                              traiettorie_matrice, stop[incrID], x_auto_in_celle,
                                              y_auto_in_celle)

                            passaggio[incrID] = info[0]
                            attesa[incrID] = info[1]
                            ferme[incrID] = info[2]
                            matrice_incrocio[incrID] = info[3]
                            passaggio_cella[incrID] = info[4]
        # riaccelero i veicoli all'uscita dall'incrocio
        if int(step / step_incr) % 10 == 0:
            for auto_uscita in passaggio_precedente[incrID]:
                if auto_uscita not in passaggio[incrID]:
                    # da guardare
                    traci.vehicle.setMaxSpeed(auto_uscita[0], 13.888888)
                    traci.vehicle.setSpeed(auto_uscita[0], 13.888888)
                    traci.vehicle.setSpeedMode(auto_uscita[0], 7)
            passaggio_precedente[incrID] = passaggio[incrID][:]
        # ogni 10 step pulisco la matrice da valori troppo vecchi
        if int(step / step_incr) % 10 == 0:
            matrice_incrocio = pulisci_matrice(matrice_incrocio, secondi_di_sicurezza)

        step += step_incr
        n_step += 1
        # faccio avanzare la simulazione
        traci.simulationStep(step)
        # inserisco nell'array le auto presenti nella simulazione
        arrayAuto = costruzioneArray(arrayAuto)

        if n_step % sec == 0:
            vehs_loaded = traci.vehicle.getIDList()
            for lane in tails_per_lane:
                tails_per_lane[lane].append(0)
                # supponendo che period sia sempre multiplo di 5
                if n_step % (period * sec) == 0:
                    # print(f"Counter Serving: {counter_serving[lane]}, Counter Served: {counter_served[lane]}")
                    serving[lane].append(counter_serving[lane])
                    served[lane].append(counter_served[lane])
                    # print(f"Serving: {serving[lane]}, Served: {served[lane]}, Lane: {lane}")
                    counter_serving[lane] -= counter_served[lane]
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
                    if traci.vehicle.getSpeed(veh) <= 2:
                        tails_per_lane[vehicles[veh]['startingLane']][int(n_step / sec) - 1] += 1
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
                        # print(f"Veicolo {veh} è stato servito")
                        counter_served[vehicles[veh]['startingLane']] += 1
                        vehicles[veh]['hasCrossed'] = 1
                    if schema in ['s', 'S']:
                        traci.vehicle.setColor(veh, (0, 255, 0))  # verde
                # controllo se il veicolo è in una lane entrante
                if veh_current_lane[4:6] == '07':
                    vehicles[veh]['startingLane'] = veh_current_lane
                    vehicles[veh]['speeds'].append(traci.vehicle.getSpeed(veh))
                    spawn_distance = traci.vehicle.getDistance(veh)
                    # print(f"Lane: {veh_current_lane}, Vehicle: {veh}")
                    distance = getDistanceFromLaneEnd(spawn_distance, traci.lane.getLength(veh_current_lane),
                                                      junction_shape)
                    veh_length = traci.vehicle.getLength(veh)
                    check = veh_length / 2 + 0.2
                    leader = traci.vehicle.getLeader(veh)
                    if vehicles[veh]['hasEntered'] == 0:
                        # print(f"Veicolo {veh} deve essere servito")
                        counter_serving[veh_current_lane] += 1
                        vehicles[veh]['hasEntered'] = 1
                    if traci.vehicle.getSpeed(veh) <= 1:
                        # verifico se il veicolo si è fermato al di fuori del punto di spawn
                        if spawn_distance > 0:
                            vehicles[veh]['hasStopped'] = 1
                            tails_per_lane[veh_current_lane][int(n_step / sec) - 1] += 1
                        # verifico se il veicolo è in testa
                        if check >= distance and ((leader and leader[1] > 0.5 and
                                                   vehicles[leader[0]]['startingLane'] != veh_current_lane)
                                                  or not leader):
                            vehicles[veh]['headStopTime'] += 1
                            if schema in ['s', 'S']:
                                traci.vehicle.setColor(veh, (0, 0, 255))  # blu
                            continue
                        # verifico se il veicolo è in coda
                        if leader and leader[1] <= 0.5 and vehicles[leader[0]]['startingLane'] == veh_current_lane:
                            vehicles[veh]['followerStopTime'] += 1
                            if schema in ['s', 'S']:
                                traci.vehicle.setColor(veh, (255, 0, 0))  # rosso
                            continue
                    else:
                        if schema in ['s', 'S']:
                            traci.vehicle.setColor(veh, (255, 255, 0))  # giallo
    if n_step % (period * sec) != 0:
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
        # print(f"Serving: {serving[lane]}, Served: {served[lane]}, Lane: {lane}")
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

    queue.put([int(step), meanHeadTime, varHeadTime, max(headTimes), meanTailTime, varTailTime,
               max(tailTimes), meanSpeed, varSpeed, maxSpeed, meanTail, varTail, maxTail, sum(nStoppedVehicles),
               meanTP])


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
        sumoCmd = [sumoBinary, "-c", config_file, "--time-to-teleport", "-1", "--step-length", "0.025"]
    else:
        sumoBinary = checkBinary('sumo-gui')
        sumoCmd = [sumoBinary, "-c", config_file, "--time-to-teleport", "-1", "-S", "-Q", "--step-length", "0.025"]
        choice = ''
        while choice not in ['s', 'S', 'n', 'N']:
            choice = input('\nDesideri visualizzare le auto con uno schema di colori significativo? (s, n): ')
            if choice not in ['s', 'S', 'n', 'N']:
                print('\nInserire un carattere tra s e n!')
        schema = choice
    numberOfSimulations = checkInput(1, '\nInserire il numero di simulazioni: ',
                                     f'\nUtilizzo una simulazione come default...',
                                     '\nInserire un numero di simulazioni positivo!')

    measures = {}
    measures['total_time'] = []
    measures['total_time'].append({'label': 'Tempo totale (s)', 'color': '#DF1515', 'title': 'total_time',
                                   'values': []})
    measures['head_time'] = []
    measures['head_time'].append(
        {'label': 'Tempo medio in testa (s)', 'color': '#DF1515', 'title': 'mean_head_time', 'values': []})
    measures['head_time'].append(
        {'label': 'Deviazione standard tempo in testa (s)', 'color': '#1524DF', 'title': 'st_dev_head_time',
         'values': []})
    measures['head_time'].append(
        {'label': 'Massimo tempo in testa (s)', 'color': '#15DF1E', 'title': 'max_head_time', 'values': []})
    measures['tail_time'] = []
    measures['tail_time'].append(
        {'label': 'Tempo medio in coda (s)', 'color': '#DF1515', 'title': 'mean_tail_time', 'values': []})
    measures['tail_time'].append(
        {'label': 'Deviazione standard tempo in coda (s)', 'color': '#1524DF', 'title': 'st_dev_tail_time',
         'values': []})
    measures['tail_time'].append(
        {'label': 'Massimo tempo in coda (s)', 'color': '#15DF1E', 'title': 'max_tail_time', 'values': []})
    measures['speed'] = []
    measures['speed'].append(
        {'label': 'Velocità media (m/s)', 'color': '#DF1515', 'title': 'mean_speed', 'values': []})
    measures['speed'].append(
        {'label': 'Deviazione standard velocità (m/s)', 'color': '#1524DF', 'title': 'st_dev_speed',
         'values': []})
    measures['speed'].append(
        {'label': 'Massima velocità (m/s)', 'color': '#15DF1E', 'title': 'max_speed', 'values': []})
    measures['tail_length'] = []
    measures['tail_length'].append(
        {'label': 'Lunghezza media delle code', 'color': '#DF1515', 'title': 'mean_tail_length', 'values': []})
    measures['tail_length'].append(
        {'label': 'Deviazione standard lunghezza delle code', 'color': '#1524DF', 'title': 'st_dev_tail_length',
         'values': []})
    measures['tail_length'].append(
        {'label': 'Massima lunghezza delle code', 'color': '#15DF1E', 'title': 'max_tail_length', 'values': []})
    measures['stopped_vehicles'] = []
    measures['stopped_vehicles'].append({'label': 'Veicoli fermi', 'color': '#DF1515', 'title': 'stopped_vehicles',
                                         'values': []})
    measures['throughput'] = []
    measures['throughput'].append({'label': f'Throughput medio (% veicoli / {period} step', 'color': '#DF1515',
                                   'title': 'mean_throughput', 'values': []})

    root = os.path.abspath(os.path.split(__file__)[0])
    path = os.path.join(root, "output_no_batch")
    if not os.path.exists(path):
        try:
            os.mkdir(path)
        except OSError:
            print(f"\nCreazione della cartella {path} fallita...")
    output_file = os.path.join(path, f'no_batch.txt')
    f = open(output_file, "w")

    tempo_generazione = 43.2  # fissato
    celle_per_lato = 20  # per protocolli basati sulla suddivisione matriciale dell'incrocio
    secondi_di_sicurezza = 0.6
    gui = False

    print("\nCalcolo la matrice di celle a partire da tutte le traiettorie possibili...")

    traiettorie_matrice = Traiettorie.run(gui, celle_per_lato)

    queue = Queue()

    for i in range(1, numberOfSimulations + 1):
        port = miscutils.getFreeSocketPort()
        sumoCmd.append("--remote-port")
        sumoCmd.append(str(port))
        numberOfVehicles = checkInput(50, f'\nInserire il numero di veicoli nella simulazione {i}: ',
                                      f'\nUtilizzo la simulazione {i} con 50 veicoli di default...',
                                      '\nInserire un numero di veicoli positivo!')
        labels_per_sims.append(f'Sim. {i} ({numberOfVehicles} veicoli)')

        run(numberOfVehicles, schema, sumoCmd, tempo_generazione, celle_per_lato, traiettorie_matrice,
            secondi_di_sicurezza, path, i, queue)

        ret = queue.get()
        output.writeMeasuresToFile(f, i, numberOfVehicles, ret)

        measures['total_time'][0]['values'].append(round(ret[0], 2))
        measures['head_time'][0]['values'].append(round(ret[1], 2))
        measures['head_time'][1]['values'].append(round(sqrt(ret[2]), 2))
        measures['head_time'][2]['values'].append(round(ret[3], 2))
        measures['tail_time'][0]['values'].append(round(ret[4], 2))
        measures['tail_time'][1]['values'].append(round(sqrt(ret[5]), 2))
        measures['tail_time'][2]['values'].append(round(ret[6], 2))
        measures['speed'][0]['values'].append(round(ret[7], 2))
        measures['speed'][1]['values'].append(round(sqrt(ret[8]), 2))
        measures['speed'][2]['values'].append(round(ret[9], 2))
        measures['tail_length'][0]['values'].append(round(ret[10], 2))
        measures['tail_length'][1]['values'].append(round(sqrt(ret[11]), 2))
        measures['tail_length'][2]['values'].append(round(ret[12], 2))
        measures['stopped_vehicles'][0]['values'].append(round(ret[13], 2))
        measures['throughput'][0]['values'].append(round(ret[14], 2))

    f.close()

    values = []
    labels = []
    titles = []
    colors = []
    arr = []
    for k in measures:
        arr.append(len(measures[k]))
        titles.append(k)
        for i in range(0, len(measures[k])):
            values.append(measures[k][i]['values'])
            labels.append(measures[k][i]['label'])
            colors.append(measures[k][i]['color'])

    output.histPerMeasures(values, labels, titles, colors, arr, labels_per_sims, path)