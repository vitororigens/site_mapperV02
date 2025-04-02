import React, { useState } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Container from '@mui/material/Container';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import HistoryIcon from '@mui/icons-material/History';
import MapeamentoForm from './components/MapeamentoForm';
import StatusMapeamento from './components/StatusMapeamento';
import HistoricoModal from './components/HistoricoModal';
import 'bootstrap/dist/css/bootstrap.min.css';

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
  const [showHistorico, setShowHistorico] = useState(false);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth="md">
        <Box sx={{ my: 4 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
            <Typography variant="h4" component="h1">
              Mapeador de Sites
            </Typography>
            <Button
              variant="contained"
              startIcon={<HistoryIcon />}
              onClick={() => setShowHistorico(true)}
            >
              Histórico
            </Button>
          </Box>
          <Typography variant="subtitle1" gutterBottom align="center" color="text.secondary">
            Ferramenta para mapeamento e formatação de sites em planilhas Excel
          </Typography>
          
          <Box sx={{ mt: 4 }}>
            <MapeamentoForm onJobCreated={setJobId} />
            {jobId && <StatusMapeamento jobId={jobId} />}
          </Box>
        </Box>
      </Container>
      <HistoricoModal show={showHistorico} onHide={() => setShowHistorico(false)} />
    </ThemeProvider>
  );
}

export default App;
