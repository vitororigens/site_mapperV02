import React, { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Paper,
  Typography,
  Grid,
  CircularProgress,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import axios from 'axios';

interface MapeamentoFormProps {
  onJobCreated: (jobId: string) => void;
}

const MapeamentoForm: React.FC<MapeamentoFormProps> = ({ onJobCreated }) => {
  const [url, setUrl] = useState('');
  const [sitePrefix, setSitePrefix] = useState('');
  const [concurrentRequests, setConcurrentRequests] = useState('10');
  const [rateLimit, setRateLimit] = useState('5');
  const [formatarPlanilha, setFormatarPlanilha] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await axios.post('http://localhost:8000/api/mapeamento', {
        url,
        site_prefix: sitePrefix,
        concurrent_requests: parseInt(concurrentRequests),
        rate_limit: parseInt(rateLimit),
        formatar_planilha: formatarPlanilha,
      });

      onJobCreated(response.data.job_id);
    } catch (err) {
      setError('Erro ao iniciar o mapeamento. Verifique a URL e tente novamente.');
      console.error('Erro:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Paper elevation={3} sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        Configuração do Mapeamento
      </Typography>
      <form onSubmit={handleSubmit}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <TextField
            fullWidth
            label="URL do Site"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
            placeholder="https://exemplo.com"
            error={!!error}
            helperText={error}
          />
          <TextField
            fullWidth
            label="Prefixo do Site"
            value={sitePrefix}
            onChange={(e) => setSitePrefix(e.target.value)}
            placeholder="Nome do Site para substituir 'Raiz'"
          />
          <Box sx={{ display: 'flex', gap: 3 }}>
            <TextField
              fullWidth
              label="Requisições Concorrentes"
              type="number"
              value={concurrentRequests}
              onChange={(e) => setConcurrentRequests(e.target.value)}
              inputProps={{ min: 1, max: 50 }}
            />
            <TextField
              fullWidth
              label="Requisições por Segundo"
              type="number"
              value={rateLimit}
              onChange={(e) => setRateLimit(e.target.value)}
              inputProps={{ min: 1, max: 20 }}
            />
          </Box>
          <FormControlLabel
            control={
              <Checkbox
                checked={formatarPlanilha}
                onChange={(e) => setFormatarPlanilha(e.target.checked)}
                color="primary"
              />
            }
            label="Formatar Planilha de Resultados"
          />
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              type="submit"
              variant="contained"
              color="primary"
              disabled={loading}
              startIcon={loading ? <CircularProgress size={20} /> : null}
            >
              {loading ? 'Iniciando...' : 'Iniciar Mapeamento'}
            </Button>
            <Button
              type="button"
              variant="outlined"
              color="secondary"
              onClick={() => {
                setUrl('');
                setSitePrefix('');
                setConcurrentRequests('10');
                setRateLimit('5');
                setFormatarPlanilha(true);
                setError('');
              }}
            >
              Limpar Formulário
            </Button>
          </Box>
        </Box>
      </form>
    </Paper>
  );
};

export default MapeamentoForm; 