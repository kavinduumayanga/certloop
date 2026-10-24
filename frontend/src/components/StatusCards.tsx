import{Box,Card,CardContent,Typography}from'@mui/material';import type{Batch,Status}from'../types';
const colors:Record<string,string>={TOTAL:'#132238',PENDING:'#64748b',SENDING:'#2563eb',SENT:'#14866d',FAILED:'#c2413b',UNCERTAIN:'#b7791f'}
export default function StatusCards({batch}:{batch:Batch}){return <Box sx={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(130px,1fr))',gap:1.5}}>{(['TOTAL','PENDING','SENDING','SENT','FAILED','UNCERTAIN']as const).map(k=><Card variant="outlined" key={k}><CardContent sx={{p:'14px!important'}}><Typography variant="caption" color="text.secondary">{k[0]+k.slice(1).toLowerCase()}</Typography><Typography variant="h5" sx={{color:colors[k]}}>{batch.counts[k]??0}</Typography></CardContent></Card>)}</Box>}

