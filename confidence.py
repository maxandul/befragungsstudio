"""Punktweise 95%-Intervalle unter unabhängigen Stichprobenannahmen.

Keine Korrektur für Nichtteilnahme, endliche Grundmengen oder Mehrfachvergleiche.
Die t-Grenzen bleiben rechnerisch unverändert, auch ausserhalb der Antwortskala.
"""
from functools import lru_cache
from math import fsum, sqrt
from statistics import NormalDist, variance

from scipy.special import stdtrit


@lru_cache(maxsize=2048)
def t_critical(df):
    return float(stdtrit(df, 0.975))


def scale_intervals(values, threshold):
    n=len(values)
    if not n:
        return dict(mean_ci95=None,top2_ci95=None)
    mean_ci=None
    if n>=2:
        mean=fsum(values)/n
        margin=t_critical(n-1)*sqrt(variance(values)/n)
        mean_ci=[mean-margin,mean+margin]
    p=sum(value>=threshold for value in values)/n
    z=NormalDist().inv_cdf(0.975)
    denominator=1+z*z/n
    center=(p+z*z/(2*n))/denominator
    margin=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
    return dict(mean_ci95=mean_ci,
                top2_ci95=[100*max(0,center-margin),100*min(1,center+margin)])
