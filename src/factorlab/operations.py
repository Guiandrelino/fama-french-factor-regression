"""Executor limitado para tarefas numéricas, sem chamadas Streamlit nos workers."""

from concurrent.futures import ThreadPoolExecutor

EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="factorlab")


def classify_error(exc):
    import requests

    if isinstance(exc, (ConnectionError, TimeoutError, requests.RequestException)):
        return "REDE", "Verifique conexão, DNS e disponibilidade do provedor."
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return "DADOS / PARÂMETROS", "Revise a central de qualidade e os parâmetros."
    return "CÁLCULO / SISTEMA", "Consulte os logs; não utilize resultados parciais."
