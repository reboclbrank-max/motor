import unittest,urllib.request
from unittest.mock import patch,Mock
import comum as C
class URLs(unittest.TestCase):
 def test_sem_credencial_nem_protocolos_locais(self):
  with patch.object(C,'host_publico') as dns:
   for u in ['https://user:SENTINELA@example.com/','file:///etc/passwd','ftp://example.com/x','https://example.com:99999','https://example.com/\nsecreto']:
    with self.assertRaises(C.URLPublicaNegada):C._validar_url_publica(u)
   dns.assert_not_called()
 def test_ips_nao_globais(self):
  for ip in ['127.0.0.1','10.0.0.1','169.254.169.254','100.64.0.1','::1','fc00::1','0.0.0.0']:
   with patch.object(C.socket,'getaddrinfo',return_value=[(2,1,6,'',(ip,80))]):self.assertFalse(C.host_publico('host'))
 def test_dns_vazio_ou_misto(self):
  for ips in [[],['8.8.8.8','127.0.0.1']]:
   with patch.object(C.socket,'getaddrinfo',return_value=[(2,1,6,'',(ip,80)) for ip in ips]):self.assertFalse(C.host_publico('host'))
 def test_redirect_checado_antes_de_nova_requisicao(self):
  h=C._RedirectPublico();req=urllib.request.Request('https://example.com')
  with patch.object(C,'host_publico',side_effect=lambda host:host=='example.com'):
   with self.assertRaises(C.URLPublicaNegada):h.redirect_request(req,None,302,'moved',{},'http://127.0.0.1/private')
   novo=h.redirect_request(req,None,302,'moved',{},'https://example.com/novo');self.assertEqual(novo.full_url,'https://example.com/novo')
 def test_verificar_nao_abre_loopback(self):
  with patch.object(C,'host_publico',return_value=False),patch.object(C.urllib.request,'build_opener') as abrir:
   self.assertIn('bloqueada',C.ferramenta_verificar('http://127.0.0.1'));abrir.assert_not_called()
 def test_abrir_nao_manda_redirect_bloqueado_ao_leitor(self):
  with patch.object(C,'host_publico',return_value=True),patch.object(C,'_buscar_bytes',side_effect=C.URLPublicaNegada('bloqueado')),patch.object(C,'_ler_via_jina') as leitor:
   self.assertIn('bloqueado',C.abrir_url('https://example.com')[1]);leitor.assert_not_called()
if __name__=='__main__':unittest.main()
