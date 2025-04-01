import React, { useState } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Container from '@mui/material/Container';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import MapeamentoForm from './components/MapeamentoForm';
import StatusMapeamento from './components/StatusMapeamento';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

function App() {
  const [jobId, setJobId] = useState<string | null>(null);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth="md">
        <Box sx={{ my: 4 }}>
          <Typography variant="h4" component="h1" gutterBottom align="center">
            Mapeador de Sites
          </Typography>
          <Typography variant="subtitle1" gutterBottom align="center" color="text.secondary">
            Ferramenta para mapeamento e formatação de sites em planilhas Excel
          </Typography>
          
          <Box sx={{ mt: 4 }}>
            <MapeamentoForm onJobCreated={setJobId} />
            {jobId && <StatusMapeamento jobId={jobId} />}
          </Box>
        </Box>
      </Container>
    </ThemeProvider>
  );
}

export default App;
