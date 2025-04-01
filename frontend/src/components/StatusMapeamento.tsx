import React, { useEffect, useState } from 'react';
import {
  Paper,
  Typography,
  LinearProgress,
  Box,
  CircularProgress,
  Alert,
} from '@mui/material';
import axios from 'axios';

interface StatusMapeamentoProps {
  jobId: string;
}

interface JobStatus {
  status: string;
  progress: number;
  message: string;
}

const StatusMapeamento: React.FC<StatusMapeamentoProps> = ({ jobId }) => {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await axios.get(`http://localhost:8000/api/mapeamento/${jobId}`);
        setStatus(response.data);
        
        // Se o job ainda não estiver concluído ou com erro, continua verificando
        if (response.data.status === 'em_andamento' || response.data.status === 'iniciando') {
          setTimeout(fetchStatus, 2000); // Verifica a cada 2 segundos
        }
      } catch (err) {
        setError('Erro ao buscar status do mapeamento');
        console.error('Erro:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();
  }, [jobId]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!status) {
    return null;
  }

  const getStatusColor = () => {
    switch (status.status) {
      case 'concluido':
        return 'success';
      case 'erro':
        return 'error';
      case 'em_andamento':
      case 'iniciando':
        return 'primary';
      default:
        return 'primary';
    }
  };

  return (
    <Paper elevation={3} sx={{ p: 3, mt: 3 }}>
      <Typography variant="h6" gutterBottom>
        Status do Mapeamento
      </Typography>
      
      <Box sx={{ mt: 2 }}>
        <Typography variant="body1" gutterBottom>
          {status.message}
        </Typography>
        
        {(status.status === 'em_andamento' || status.status === 'iniciando') && (
          <LinearProgress
            variant="determinate"
            value={status.progress}
            color={getStatusColor()}
            sx={{ mt: 2 }}
          />
        )}
        
        {status.status === 'concluido' && (
          <Alert severity="success" sx={{ mt: 2 }}>
            Mapeamento concluído com sucesso!
          </Alert>
        )}
        
        {status.status === 'erro' && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {status.message}
          </Alert>
        )}
      </Box>
    </Paper>
  );
};

export default StatusMapeamento; 