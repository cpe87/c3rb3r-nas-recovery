"""Local-only tests. Never connects to a NAS or opens raw devices."""
import pathlib,sys,tempfile,unittest
import app
sys.path.insert(0,str(pathlib.Path(__file__).parent/'engine'))
import retained_extents as p
class Checks(unittest.TestCase):
 def test_roots(self):
  self.assertEqual(app.roots_checked(['/volume1/photo/a','/volume1/photo']),['/volume1/photo'])
  for bad in ['/etc','/volume1/photo/../homes','/volume1//photo']:
   with self.assertRaises(ValueError):app.roots_checked([bad])
 def test_destination(self):
  root=pathlib.Path(tempfile.gettempdir())/'public-recovery-tests'
  self.assertEqual(app.destination(root,'/volume1/photo/a.mp4'),root/'volume1/photo/a.mp4')
  for bad in ['/volume1/../escape','/etc/passwd']:
   with self.assertRaises(ValueError):app.destination(root,bad)
  self.assertNotEqual(app.destination(root,'/volume1/photo/a:b'),app.destination(root,'/volume1/photo/a%3Ab'))
 def test_footer(self):
  tail=bytearray(588);tail[568:572]=bytes.fromhex('12345678');tail[572]=0x24;tail[574:576]=b'\x20\x00';tail[580:588]=(4096).to_bytes(8,'little')
  self.assertEqual(p.parse_footer(tail,4684,'12345678')['encrypted'],[[0,4096]])
  with self.assertRaises(p.Rejected):p.parse_footer(tail,4684,'87654321')
  with self.assertRaises(p.Rejected):p.parse_footer(tail,4684)
 def test_crc(self):self.assertEqual(p.crc32c(b'123456789'),0xe3069283)
 def test_languages(self):
  self.assertTrue(all(len(v)==2 and all(v) for v in app.TEXT.values()))
if __name__=='__main__':unittest.main()
