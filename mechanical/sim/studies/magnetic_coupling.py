"""Magnetic plunger coupling study (2026-11-19): shear force of N52 magnet pairs through the reservoir wall.
Requires: pip install magpylib magpylib-force. Result: ~1.2 N max in the existing plunger (need ~1.6 N to move, ~7 N with
occlusion back-pressure and safety factor) -> magnetic coupling rejected, see spec section 3b. Water only, bench test project."""
warnings.filterwarnings("ignore")
from magpylib_force import getFT
Br=1.43
def arr(n,L,ty,tz,y0,dx=0,sign=1):
    c=magpy.Collection()
    w=L/n
    for i in range(n):
        m=magpy.magnet.Cuboid(polarization=(0,sign*Br*(1 if i%2==0 else -1),0),dimension=(w*1e-3,ty*1e-3,tz*1e-3),
          position=((dx-L/2+w*(i+0.5))*1e-3,y0*1e-3,0))
        m.meshing=(6,6,6); c.add(m)
    return c
def shear(n,L,typ,tyc,tz,gap):
    best=0
    for dx in np.linspace(0,L/n*1.5,16):
        P=arr(n,L,typ,tz,-typ/2); C=arr(n,L,tyc,tz,gap+tyc/2,dx)
        F=sum(getFT(P,m)[0] for m in C.children)
        best=max(best,abs(F[0]))
    return best
# plunger axial length available ~3.5 mm (plunger 3.8), z height <= 3.4 mm (bore 5), plunger-side thickness up to 6 mm, carriage side 3 mm
for gap in (1.2,1.5):
  for n in (1,2,3):
    print(f"gap {gap} mm, {n} pole(s) in 3.5 mm: shear {shear(n,3.5,6,3,3.4,gap):.2f} N")
  for n in (2,4):
    print(f"gap {gap} mm, {n} poles in 7 mm (longer plunger): shear {shear(n,7,6,3,3.4,gap):.2f} N")
