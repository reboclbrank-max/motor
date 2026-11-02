"""Integração pública com fixtures estáticas. Sem PAT, memória ou código privado.
Falha se um unittest verde conseguir mascarar divergência do contrato.
"""
import execucao_isolada as E
CON={'etapas':['Contar lista vazia'],'casos':[{'etapa':1,'modulo':'main','funcao':'contar','args':[[]],'esperado':{'total':0},'nao_muta':True}]}
TEST='import unittest\nclass Teste(unittest.TestCase):\n def test_verde_insuficiente(self):self.assertTrue(True)\n'
def main():
 for codigo,esperado in [('def contar(xs):return {}\n',False),('def contar(xs):return {"total":len(xs)}\n',True)]:
  r=E.executar({'main.py':codigo,'test_main.py':TEST},CON)
  assert r['testes']==1 and r['aceite']['casos']==1 and r['sucesso'] is esperado,r
  print('Docker real: unittest verde; aceite '+('aprovado para implementação correta' if esperado else 'REPROVADO para bug vazio{}'))
 fs={'app.py':'import sys\nprint(sys.stdin.read().upper(),end="")\n','test_app.py':TEST}
 for texto,esperado in [('OLA',True),('INCORRETO',False)]:
  contrato={'etapas':['Converter stdin'],'casos':[{'etapa':1,'script':'app.py','entrada':'ola','esperado':texto,'codigo':0}]};r=E.executar(fs,contrato)
  assert r['sucesso'] is esperado and r['aceite']['casos']==1,r
  print('Docker real: stdout/exit CLI comparados no controlador; sucesso='+str(esperado))
 print('4cenários reais aprovados: negativo/positivo de função e CLI; nenhum fallback host.')
if __name__=='__main__':main()
