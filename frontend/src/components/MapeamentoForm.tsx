import React, { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Paper,
  Typography,
  Grid,
  CircularProgress,
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
        <Grid container spacing={3}>
          <Grid item xs={12}>
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
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Prefixo do Site"
              value={sitePrefix}
              onChange={(e) => setSitePrefix(e.target.value)}
              placeholder="Nome do Site para substituir 'Raiz'"
            />
          </Grid>
          <Grid item xs={6}>
            <TextField
              fullWidth
              label="Requisições Concorrentes"
              type="number"
              value={concurrentRequests}
              onChange={(e) => setConcurrentRequests(e.target.value)}
              inputProps={{ min: 1, max: 50 }}
            />
          </Grid>
          <Grid item xs={6}>
            <TextField
              fullWidth
              label="Requisições por Segundo"
              type="number"
              value={rateLimit}
              onChange={(e) => setRateLimit(e.target.value)}
              inputProps={{ min: 1, max: 20 }}
            />
          </Grid>
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button
                type="submit"
                variant="contained"
                color="primary"
                disabled={loading}
                startIcon={loading ? <CircularProgress size={20} /> : null}
              >
                {loading ? 'Iniciando...' : 'Iniciar Mapeamento'}
              </Button>
            </Box>
          </Grid>
        </Grid>
      </form>
    </Paper>
  );
};

export default MapeamentoForm; 