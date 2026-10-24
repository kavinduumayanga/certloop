import {createTheme} from '@mui/material/styles'
export const theme=createTheme({
  palette:{mode:'light',primary:{main:'#16697a',dark:'#0b4652'},secondary:{main:'#e8994e'},background:{default:'#f4f6f3',paper:'#fffdf8'}},
  typography:{fontFamily:'Inter, ui-sans-serif, system-ui, sans-serif',h3:{fontFamily:'Georgia,serif',fontWeight:700,letterSpacing:'-.03em'},h5:{fontFamily:'Georgia,serif',fontWeight:700}},
  shape:{borderRadius:12},
  components:{MuiButton:{styleOverrides:{root:{textTransform:'none',fontWeight:700,borderRadius:8}}},MuiPaper:{styleOverrides:{root:{backgroundImage:'none'}}}}
})

