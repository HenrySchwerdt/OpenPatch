"""Dump footprints + edge cuts of a cup board to JSON (pod-frame conversion is in make_overlay.py). usage: ../../board/kpy dump_board.py <board.kicad_pcb> <out.json>"""
import pcbnew, json, sys
sys.path.insert(0,'/Users/henryschwerdtner/dev/ai-insulin-pump-elec/electronics/v010/cup')
import cupgeom as G
from place_cup import height
b=pcbnew.LoadBoard(sys.argv[1]); T=pcbnew.ToMM
ec=b.GetBoardEdgesBoundingBox()
print("edge bbox", T(ec.GetLeft()),T(ec.GetTop()),T(ec.GetRight()),T(ec.GetBottom()))
# edge segments
segs=[]
for d in b.GetDrawings():
    if d.GetLayer()==pcbnew.Edge_Cuts:
        segs.append((T(d.GetStart().x),T(d.GetStart().y),T(d.GetEnd().x),T(d.GetEnd().y)))
print("edges",segs)
print("thickness",T(b.GetDesignSettings().GetBoardThickness()), "layers", b.GetCopperLayerCount())
out=[]
for f in b.GetFootprints():
    f.BuildCourtyardCaches()
    side='B' if f.IsFlipped() else 'F'
    c=f.GetCourtyard(pcbnew.B_CrtYd if side=='B' else pcbnew.F_CrtYd)
    bb=c.BBox() if c.OutlineCount() else f.GetBoundingBox(False,False)
    p=f.GetPosition()
    out.append(dict(ref=f.GetReference(),fp=f.GetFPID().GetLibItemName().wx_str() if hasattr(f.GetFPID().GetLibItemName(),'wx_str') else str(f.GetFPID().GetLibItemName()),
        x=T(p.x),y=T(p.y),rot=f.GetOrientationDegrees(),side=side,bb=[T(bb.GetLeft()),T(bb.GetTop()),T(bb.GetRight()),T(bb.GetBottom())],val=f.GetValue()))
for o in out: o['h']=height(o['fp'])
json.dump(dict(edges=segs,fps=out),open(sys.argv[2],'w'),indent=0)
print(len(out))
