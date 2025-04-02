import React, { useEffect, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  CircularProgress,
  Button,
  Alert,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
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
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const response = await axios.get(`http://localhost:8000/api/mapeamento/${jobId}`);
        setStatus(response.data);
        
        if (response.data.status === 'em_andamento') {
          setTimeout(checkStatus, 2000); // Verifica novamente em 2 segundos
        }
      } catch (err) {
        if (axios.isAxiosError(err)) {
          setError(err.response?.data?.detail || 'Erro ao verificar status do mapeamento');
        } else {
          setError('Erro ao verificar status do mapeamento');
        }
        console.error('Erro:', err);
      }
    };

    checkStatus();
  }, [jobId]);

  const handleDownload = async () => {
    try {
      setDownloading(true);
      setError(null);
      
      const response = await axios.get(`http://localhost:8000/api/mapeamento/${jobId}/download`, {
        responseType: 'blob'
      });
      
      // Extrair o nome do arquivo do header Content-Disposition
      const contentDisposition = response.headers['content-disposition'];
      let filename = 'SEPD.xlsx';
      if (contentDisposition) {
        const matches = /filename="(.+)"/.exec(contentDisposition);
        if (matches && matches[1]) {
          filename = matches[1];
        }
      }
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail || 'Erro ao baixar o arquivo');
      } else {
        setError('Erro ao baixar o arquivo');
      }
      console.error('Erro:', err);
    } finally {
      setDownloading(false);
    }
  };

  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!status) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Paper elevation={3} sx={{ p: 3, mt: 2 }}>
      <Typography variant="h6" gutterBottom>
        Status do Mapeamento
      </Typography>
      
      <Box sx={{ mb: 2 }}>
        <Typography color="textSecondary">
          {status.message}
        </Typography>
        {status.status === 'em_andamento' && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
            <CircularProgress size={20} />
            <Typography variant="body2">
              Progresso: {status.progress}%
            </Typography>
          </Box>
        )}
      </Box>

      {status.status === 'concluido' && (
        <Button
          variant="contained"
          color="primary"
          startIcon={downloading ? <CircularProgress size={20} /> : <DownloadIcon />}
          onClick={handleDownload}
          disabled={downloading}
        >
          {downloading ? 'Baixando...' : 'Baixar Planilha'}
        </Button>
      )}
    </Paper>
  );
};

export default StatusMapeamento; 