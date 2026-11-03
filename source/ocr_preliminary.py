from pathlib import Path
import json,fitz,numpy as np,argparse,time
from rapidocr import RapidOCR
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--year',type=int,required=True);ap.add_argument('--variant',default='clean',choices=['raw','clean']);args=ap.parse_args()
sources=json.loads((ROOT/'data/广东初赛补充来源.json').read_text(encoding='utf-8'))
s=next(s for s in sources if s['year']==args.year and s['pages']>1)
out=ROOT/f'data/初赛OCR/{args.year}-{args.variant}';out.mkdir(parents=True,exist_ok=True)
e=RapidOCR(params={'Global.log_level':'error','Det.limit_side_len':1500,'Det.limit_type':'max','Rec.rec_batch_num':64,
                  'EngineConfig.onnxruntime.intra_op_num_threads':2,'EngineConfig.onnxruntime.inter_op_num_threads':1})
doc=fitz.open(ROOT/s['local'])
for ix,page in enumerate(doc):
    dest=out/f'p{ix+1:03}.json'
    if dest.exists():continue
    started=time.time();pix=page.get_pixmap(matrix=fitz.Matrix(2.5,2.5),alpha=False)
    a=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3).copy()
    if args.variant=='clean':
        red=(a[:,:,0].astype(float)>a[:,:,1]*1.15)&(a[:,:,0].astype(float)>a[:,:,2]*1.15)
        a[red]=255
    r=e(a)
    boxes=[] if r.boxes is None else [[b.tolist(),t,float(score)] for b,t,score in zip(r.boxes,r.txts,r.scores)]
    data=dict(page=ix+1,scale=2.5,source=s['local'],variant=args.variant,boxes=boxes,seconds=round(time.time()-started,2))
    dest.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    if ix%5==0 or ix+1==len(doc):print(args.year,args.variant,ix+1,'/',len(doc),'boxes',len(boxes),data['seconds'],flush=True)
