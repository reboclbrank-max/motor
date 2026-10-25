#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Manutenção da memória do assistente — para o dono rodar quando quiser:

  - backup:   faz agora a cópia de segurança do dia (MEMORIA/backup/AAAA-MM-DD.json)
  - resumo:   gera agora o panorama geral da memória (MEMORIA/resumo-geral.md)
  - avisos:   confere agora todos os avisos e lembretes (e entrega o que venceu)
  - teste:    manda um aviso de teste (para ver se chega em você)
  - tudo:     backup + resumo (padrão)

No GitHub: Actions → "Manutenção da memória" → Run workflow.
"""
import os
import sys

import comum as C


def principal():
    acao = (os.environ.get("MANUTENCAO") or "tudo").strip().lower()
    feitos = []
    if acao in ("backup", "tudo"):
        if C.backup_memoria():
            feitos.append("backup do dia gravado ✓")
    if acao in ("avisos", "teste"):
        try:
            resultado = C.checar_avisos()
            lembretes = C.checar_lembretes()
            feitos.append(f"avisos conferidos: {resultado.get('ativos', 0)} ativo(s), "
                          f"{len(resultado.get('disparados', []))} disparado(s), "
                          f"{len(lembretes)} lembrete(s) entregue(s)")
            if resultado.get("erros"):
                feitos.append("erros: " + "; ".join(resultado["erros"][:3]))
        except Exception as e:
            feitos.append(f"avisos falharam ({str(e)[:80]})")
    if acao == "teste":
        try:
            canais = C.notificar("Teste de aviso", "Teste pedido pelo dono na Manutenção — se chegou, os avisos "
                                                   "estão funcionando.", tipo="teste")
            feitos.append("teste enviado por: " + (", ".join(canais) or "nenhum canal"))
        except Exception as e:
            feitos.append(f"teste falhou ({str(e)[:80]})")
    if acao == "resumo":
        try:
            C.resumir_memoria()
            feitos.append("panorama geral atualizado ✓")
        except Exception as e:
            feitos.append(f"panorama falhou ({str(e)[:80]})")
    C.log("manutenção: " + (", ".join(feitos) or "nada a fazer"))
    print("manutenção:", ", ".join(feitos) or "nada a fazer")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
