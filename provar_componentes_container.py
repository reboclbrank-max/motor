"""Fixtures públicas: baseline realmente extraído e referência confiável, nunca código privado."""
import inspect
import chat_componentes as F,execucao_isolada as E

def main():
 fs={'formatador.py':F.BASELINE,'test_api.py':F.TESTE}
 r=E.executar(fs,F.contrato());assert not r['sucesso'] and r['testes']==2 and r['aceite']['casos']==11
 print('Componente Docker: baseline legado falha no contrato reforçado, unittest nominal verde.')
 fonte='import re\n'+inspect.getsource(F.escapar)+'\n'+inspect.getsource(F.referencia).replace('def referencia(', 'def formatar(')
 r=E.executar({'formatador.py':fonte,'test_api.py':F.TESTE},F.contrato());assert r['sucesso'] and r['aceite']['casos']==11
 print('Componente Docker: referência confiável passa11casos; comparação no controlador, sem segredos.')
if __name__=='__main__':main()
