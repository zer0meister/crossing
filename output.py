import os
import numpy as np
import matplotlib.pyplot as plt
from datetime import date
from math import sqrt


def writeMeasuresToFile(f, i, numberOfVehicles, ret):
    """Salvo su un file le misure effettuate"""
    f.write('----------------------------------------------------\n')
    f.write(f'\nSIMULAZIONE NUMERO {i}\n')
    f.write('\n----------------------------------------------------\n')
    f.write(f'\nNUMERO DI VEICOLI: {numberOfVehicles}\n')
    f.write(f'\nTEMPO TOTALE DI SIMULAZIONE: {ret[0]} step\n')
    f.write(f'\nTEMPO MEDIO PASSATO IN TESTA A UNA CORSIA: {round(ret[1], 2)} step\n')
    f.write(
        f'\nDEVIAZIONE STANDARD DEL TEMPO PASSATO IN TESTA A UNA CORSIA: {round(sqrt(ret[2]), 2)} step\n')
    f.write(f'\nTEMPO MASSIMO PASSATO IN TESTA A UNA CORSIA: {ret[3]} step\n')
    f.write(f'\nTEMPO MEDIO PASSATO IN CODA: {round(ret[4], 2)} step\n')
    f.write(
        f'\nDEVIAZIONE STANDARD DEL TEMPO PASSATO IN CODA A UNA CORSIA: {round(sqrt(ret[5]), 2)} step\n')
    f.write(f'\nTEMPO MASSIMO PASSATO IN CODA: {ret[6]} step\n')
    f.write(f'\nVELOCITA MEDIA DEI VEICOLI: {round(ret[7], 2)} m/s\n')
    f.write(f'\nDEVIAZIONE STANDARD VELOCITA MEDIA DEI VEICOLI: {round(sqrt(ret[8]), 2)} m/s\n')
    f.write(f'\nVELOCITA MASSIMA DEI VEICOLI: {round(ret[9], 2)} m/s\n')
    f.write(f'\nLUNGHEZZA MEDIA DELLE CODE: {round(ret[10], 2)} auto\n')
    f.write(f'\nDEVIAZIONE STANDARD LUNGHEZZA DELLE CODE: {round(sqrt(ret[11]), 2)} m/s\n')
    f.write(f'\nLUNGHEZZA MASSIMA DELLE CODE: {round(ret[12], 2)} auto\n')
    f.write(
        f'\nNUMERO DI VEICOLI FERMI: {ret[13]} ({round(ret[13] / numberOfVehicles * 100, 2)}%)\n')
    f.write(f'\nTHROUGHPUT MEDIO: {round(ret[14], 2)}\n\n')


def autolabel(values, r, offset, ax):
    """Funzione per mettere il numero sopra la barra dell'istogramma"""

    i = 0
    for value in values:
        ax.annotate(f'{value}',
                    xy=(r[i] + offset, value),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')
        i += 1


def histPerMeasures(values, labels, titles, colors, arr, labels_per_sims, path, project=''):
    """Salvo su immagini gli istogrammi con le misure medie per ogni simulazione"""

    j = 0
    for i in range(0, len(arr)):
        sx = 0
        dx = 0
        c = arr[i]
        r = np.arange(len(values[i]))
        fig, ax = plt.subplots()
        # controllo se è pari
        if arr[i] % 2 == 0:
            c -= 2
            sx = -0.1
            dx = 0.1
            ax.plot(r + sx, values[j], color=colors[j], label=labels[j], lw=2, marker='s')
            autolabel(values[j], r, sx, ax)
            j += 1
            ax.plot(r + dx, values[j], color=colors[j], label=labels[j], lw=2, marker='s')
            autolabel(values[j], r, dx, ax)
            j += 1
        else:
            c -= 1
            ax.plot(r, values[j], color=colors[j], label=labels[j], lw=2, marker='s')
            autolabel(values[j], r, 0, ax)
            j += 1
        for k in range(0, int(c / 2)):
            sx -= 0.2
            ax.plot(r + sx, values[j], color=colors[j], label=labels[j], lw=2, marker='s')
            autolabel(values[j], r, sx, ax)
            j += 1
            dx += 0.2
            ax.plot(r + dx, values[j], color=colors[j], label=labels[j], lw=2, marker='s')
            autolabel(values[j], r, dx, ax)
            j += 1
        plt.ylabel("Valori")
        ax.set_xticks(r)
        ax.set_title(project)
        ax.set_xticklabels(labels_per_sims)
        ax.legend(title='Legenda', bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
        plt.savefig(path + "/" + titles[i] + '_' + date.today().strftime("%d-%m-%Y") + '.png', bbox_inches='tight')
