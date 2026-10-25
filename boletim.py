"""Boletim diário da casa: saúde dos motores + janelas + estudos + fila, em 1 mensagem no Telegram."""
import json

import comum


def main():
    linhas = ["📋 Boletim Rebocl Brank — bom dia, chefe!"]
    try:
        saude = json.loads(comum.ler_remoto("MEMORIA/saude-motores.json", "{}") or "{}")
        vivos, total = saude.get("vivos"), saude.get("total")
        quando = (saude.get("quando") or "")[:16]
        if vivos is not None:
            linhas.append(f"💓 Motores: {vivos}/{total} vivos (raio-X {quando}Z)")
            mortos = saude.get("mortos") or []
            if mortos:
                linhas.append("   Fora: " + ", ".join(mortos[:6]) + ("…" if len(mortos) > 6 else ""))
    except Exception:
        pass
    try:
        jan = (comum.ler_remoto("MEMORIA/janelas.md", "") or "").strip().splitlines()
        dados = [l for l in jan if l.startswith("| 1") or l.startswith("| 0")]
        if dados:
            linhas.append("🪟 Última caçada: " + " · ".join(x.strip("| ") for x in dados[-1].split("|")[1:3]))
    except Exception:
        pass
    try:
        est = json.loads(comum.ler_remoto("MEMORIA/estudo-estado.json", "{}") or "{}")
        indice = est.get("indice") or est.get("índice")
        if indice:
            linhas.append(f"📚 Estudos: índice {indice}")
    except Exception:
        pass
    linhas.append("🏛 App: https://reboclbrank-max.github.io/site/comite.html")
    comum.notificar("Boletim diário", "\n".join(linhas))
    print("\n".join(linhas))


if __name__ == "__main__":
    main()
