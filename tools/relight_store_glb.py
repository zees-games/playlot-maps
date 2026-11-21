"""Relight the Kenney/Sketchfab store glbs that draw flat or cyan: drop KHR_materials_unlit, metallic 0, roughness 0.9 (same as gs-map 6aa39fc)."""
import json,struct,sys
NATURAL={'leafsDark':[0.06,0.17,0.04,1],'grass':[0.069,0.195,0.03,1],'dirt':[0.18,0.12,0.07,1],'stone':[0.3,0.3,0.28,1],
 'stoneDark':[0.26,0.25,0.23,1],'wood':[0.25,0.14,0.07,1],'woodDark':[0.2,0.11,0.06,1],'woodBarkDark':[0.16,0.09,0.05,1]}
def run(f,write):
    d=open(f,'rb').read()
    l=struct.unpack('<I',d[12:16])[0]
    j=json.loads(d[20:20+l]); ch=False
    for m in j.get('materials',[]):
        e=m.get('extensions',{})
        if 'KHR_materials_unlit' in e:
            del e['KHR_materials_unlit']; ch=True
            if not e: m.pop('extensions')
        p=m.setdefault('pbrMetallicRoughness',{})
        nat=NATURAL.get(m.get('name'))
        if nat and 'nature-kit' in f and 'baseColorTexture' not in p:
            p['baseColorFactor']=nat; ch=True
        if p.get('metallicFactor',1)>=0.9 and 'metallicRoughnessTexture' not in p:
            p['metallicFactor']=0.0; p['roughnessFactor']=0.9; ch=True
    if j.get('extensionsUsed'):
        j['extensionsUsed']=[x for x in j['extensionsUsed'] if x!='KHR_materials_unlit'] or None
        if j['extensionsUsed'] is None: del j['extensionsUsed']
    if ch and write:
        b=json.dumps(j,separators=(',',':')).encode(); b+=b' '*((4-len(b)%4)%4)
        rest=d[20+l:]
        out=d[:8]+struct.pack('<I',12+8+len(b)+len(rest))+struct.pack('<I',len(b))+d[16:20]+b+rest
        open(f,'wb').write(out)
    return ch
for f in sys.argv[2:]: print(f,run(f,sys.argv[1]=='write'))
