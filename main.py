import importlib.util
from multiprocessing import Process, Queue
from inpout import *
from config import *
from reservation import traiettorie

from sumolib import checkBinary

if __name__ == "__main__":
    """Main che avvia un certo numero di simulazioni in parallelo (in modalità manuale o automatica)"""

    dir = f"outputs_{date.today().strftime('%d-%m-%Y')}"
    root = os.path.abspath(os.path.split(__file__)[0])
    path = os.path.join(root, dir)

    if not os.path.exists(path):
        try:
            os.mkdir(path)
        except OSError:
            print(f"\nCreazione della cartella {path} fallita...")
            sys.exit(-1)

    print("\nCalcolo per la reservation la matrice di celle a partire da tutte le traiettorie possibili...")
    traiettorie_matrice = traiettorie.run(False, celle_per_lato)

    projs = checkChoice(projects,
                        '\nQuale progetto vuoi avviare? (classic_tls, classic_precedence, reservation, '
                        'precedence_with_comp_auction, precedence_with_coop_auction): ',
                        "\nUtilizzo il semaforo classico come default...", '\nInserire un nome di progetto valido!',
                        mode, arr=True)

    for project in projs:

        project_label = projects_labels[projects.index(project)]

        try:
            module = importlib.import_module(".main", package=project)
        except Exception:
            print("\nImpossibile trovare il progetto...")
            sys.exit(-1)

        print(f"\nEseguo il progetto {project}...")

        config_file = os.path.join(os.path.split(__file__)[0], project,
                                   "intersection.sumocfg")  # file di configurazione della simulazione

        choice = checkChoice(['g', 'G', 'd', 'D'],
                             '\nVuoi raccogliere dati o avere una visualizzazione grafica? (g = grafica, '
                             'd = dati): ',
                             "\nUtilizzo la modalità dati come default...",
                             '\nInserire un carattere tra d e g!',
                             mode)

        sumoBinary = checkBinary('sumo') if choice in ['d', 'D'] else checkBinary('sumo-gui')

        sumoCmd = [sumoBinary, "-c", config_file, "--time-to-teleport", "-1"] if choice in ['d', 'D'] else \
            [sumoBinary, "-c", config_file, "--time-to-teleport", "-1", "-S", "-Q"]

        sumoDict = {'classic_tls': sumoCmd,
                    'classic_precedence': sumoCmd,
                    'reservation': sumoCmd + ["--step-length", "0.050"],
                    'precedence_with_comp_auction': sumoCmd,
                    'precedence_with_coop_auction': sumoCmd}

        schema = ''
        if choice in ['g', 'G']:
            schema = checkChoice(['s', 'S', 'n', 'N'],
                                 '\nDesideri visualizzare le auto con uno schema di colori significativo? '
                                 '(s, n): ',
                                 "\nUtilizzo lo schema significativo come default...",
                                 '\nInserire un carattere tra s e n!', mode)

        diff = checkInput(diffSim, f'\nInserire il numero di simulazioni diverse: ',
                          f'\nUtilizzo come default {diffSim} run diverse...',
                          '\nInserire un numero di simulazioni positivo!', mode,
                          f'\nEseguo {diffSim} scenari di traffico differenti...', diffSim)

        dir = os.path.join(path, project)

        if not os.path.exists(dir):
            try:
                os.mkdir(dir)
            except OSError:
                print(f"\nCreazione della cartella {dir} fallita...")
                sys.exit(-1)

        for i in range(0, diff):

            output_file = os.path.join(dir, f'{i}.txt')
            f = open(output_file, "w")

            print(f'\nUtilizzo un set di {numberOfVehicles[i]} veicoli in {stepsSpawn} steps...')

            repeat = checkInput(repeatSim, f'\nInserire il numero di ripetizioni della simulazione {i}: ',
                                f'\nUtilizzo come default {repeatSim} stesse run...',
                                '\nInserire un numero di simulazioni positivo!', mode,
                                f'\nEseguo {repeatSim} simulazioni in parallelo...', repeatSim,
                                max_inp=repeatSim)

            procs = []
            queue = Queue()

            for j in range(0, repeat):

                args = {
                    'classic_tls': (
                        numberOfVehicles[i], schema, sumoDict['classic_tls'], dir, j, queue, seeds[j]),
                    'classic_precedence': (
                        numberOfVehicles[i], schema, sumoDict['classic_precedence'], dir, j, queue, seeds[j]),
                    'reservation': (
                        numberOfVehicles[i], schema, sumoDict['reservation'], dir, j, queue, seeds[j], celle_per_lato,
                        traiettorie_matrice, secondi_di_sicurezza),
                    'precedence_with_comp_auction': (
                        numberOfVehicles[i], schema, sumoDict['precedence_with_comp_auction'], dir, j, queue, seeds[j],
                        simulationMode if simulationMode else not simulationMode, instantPay, dimensionOfGroups),
                    'precedence_with_coop_auction': (
                        numberOfVehicles[i], schema, sumoDict['precedence_with_comp_auction'], dir, j, queue, seeds[j],
                        simulationMode if not simulationMode else not simulationMode, instantPay, dimensionOfGroups)
                }

                p = Process(target=module.run, args=args[project])
                p.start()
                procs.append(p)

            for p in procs:
                p.join()

            collectMeasures(queue, repeat, sum(numberOfVehicles[i]), group_measures, single_measures, groups, titles,
                            head_titles, labels, numberOfVehicles, project, f, i)

            f.close()

        linesPerGroups(group_measures, groups, stepsSpawn, dir, project_label)

        clearMeasures(group_measures, groups, head_titles)

    linesPerMeasure(single_measures, labels, titles, colors, projects, projects_labels, numberOfVehicles, stepsSpawn,
                    path)
