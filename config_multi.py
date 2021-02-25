# Variabili di configurazione comuni

mode = 'auto'  # stringa che imposta la modalità automatica ('auto') o manuale (qualsiasi stringa) per le simulazioni
# Numero di veicoli: [[50, 50, 50, 50], [100, 100, 100, 100], [150, 150, 150, 150], [200, 200, 200, 200]]
numberOfVehicles = [[50, 50, 50, 50], [100, 100, 100, 100], [150, 150, 150, 150], [200, 200, 200, 200]]
# lista contenente il numero di veicoli generati per ogni simulazione
stepsSpawn = 200  # numero di step entro cui generare tutti i veicoli della simulazione
numberOfSteps = 250  # numero di step entro cui ogni simulazione deve terminare
# Semi: [9001, 2, 350, 39, 78, 567, 1209, 465, 21, 987]
seeds = [9001, 2, 350, 39, 78, 567, 1209, 465, 21, 987]  # semi iniziali delle simulazioni
repeatSim = len(seeds)  # numero di volte per cui la stessa simulazione deve essere ripetuta
diffSim = len(numberOfVehicles)  # numero di simulazioni diverse che devono essere eseguite

config_file = "intersection.sumocfg"  # file di configurazione della simulazione
output_redirection = True  # variabile che redireziona l'output su file (True) o su terminale (False)
tempo_generazione = 50  # tempo di generazione dei veicoli
celle_per_lato = 20  # numero di celle per lato nel caso della reservation
secondi_di_sicurezza = 0.6  # soglia tra veicoli per la reservation
simulationMode = True  # asta competitiva (True) o cooperativa (False)
instantPay = True  # i veicoli pagano subito (True) o pagano solo i vincitori delle aste (False)
dimensionOfGroups = -1  # dimensione del gruppo degli sponsor (da 1 a 7 o -1 per una dimensione variabile)

# Variabili di configurazione per ogni simulazione (più incroci)

projects_multi = ["multi_classic_tls", "multi_auction_classic_tls"]
two_way_junctions_ids = [1, 5, 21, 25]  # id degli incroci a 2 vie
three_way_junctions_ids = [2, 3, 4, 6, 10, 11, 15, 16, 20, 22, 23, 24]  # id degli incroci a 3 vie
four_way_junctions_ids = [7, 8, 9, 12, 13, 14, 17, 18, 19]  # id degli incroci a 4 vie
routeMode = True  # generazione delle route dei veicoli in modo statico (True) o dinamico (False)

labels_multi = ['Tempo medio di percorrenza (s)', 'Deviazione standard tempo di percorrenza (s)',
                'Massimo tempo di percorrenza (s)', 'Tempo medio in testa (s)',
                'Deviazione standard tempo in testa (s)', 'Massimo tempo in testa (s)', 'Tempo medio in coda (s)',
                'Deviazione standard tempo in coda (s)', 'Massimo tempo in coda (s)', 'Velocità media (m/s)',
                'Deviazione standard velocità (m/s)', 'Lunghezza media delle code',
                'Deviazione standard lunghezza delle code', 'Massima lunghezza delle code', 'Throughput medio',
                'Lunghezza media delle code (tutti gli incroci)',
                'Deviazione standard lunghezza delle code (tutti gli incroci)',
                'Massima lunghezza delle code (tutti gli incroci)',
                'Throughput medio (tutti gli incroci)']

colors_multi = ['#DF1515', '#1524DF', '#15DF1E', '#FCFF33']

head_titles_multi = ['trip_time', 'head_time', 'tail_time', 'speed', 'tail_length', 'throughput', 'tail_lengths',
                     'throughputs']

titles_multi = ['mean_trip_time', 'st_dev_trip_time', 'max_trip_time', 'mean_head_time', 'st_dev_head_time',
                'max_head_time', 'mean_tail_time', 'st_dev_tail_time', 'max_tail_time', 'mean_speed',
                'st_dev_mean_speed', 'mean_tail_length', 'st_dev_tail_length', 'max_tail_length',
                'mean_throughput', 'mean_tail_length_all', 'st_dev_tail_length_all', 'max_tail_length_all',
                'mean_throughput_all']

groups_multi = [3, 3, 3, 2, 3, 1, 3, 1]

projects_labels_multi = []

for project in projects_multi:
    if project == "multi_classic_tls":
        projects_labels_multi.append("Solo semafori")
    if project == "multi_auction_classic_tls":
        projects_labels_multi.append("Asta interna, semafori esterni")

group_measures_multi = {}

group_measures_multi['sims'] = [str(vehs) for vehs in numberOfVehicles]

i = 0
j = 0

for title in head_titles_multi:
    k = 0
    group_measures_multi[title] = []
    while k < groups_multi[i]:
        group_measures_multi[title].append({'label': labels_multi[j], 'color': colors_multi[k],
                                            'title': titles_multi[j], 'values': []})
        j += 1
        k += 1
    i += 1

single_measures_multi = {}

for vehs in numberOfVehicles:
    single_measures_multi[str(vehs)] = {}
    for i in range(0, len(labels_multi)):
        single_measures_multi[str(vehs)][labels_multi[i]] = []
        for j in range(0, len(projects_multi)):
            single_measures_multi[str(vehs)][labels_multi[i]].append({'project': projects_multi[j],
                                                                      'color': colors_multi[j], 'values': []})