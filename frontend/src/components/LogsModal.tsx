import React, { useEffect, useState } from 'react';
import { Modal, Table, Button } from 'react-bootstrap';
import { format, parse } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import axios from 'axios';

interface LogEntry {
    timestamp: string;
    level: string;
    message: string;
    job_id: string | null;
}

interface LogsModalProps {
    show: boolean;
    onHide: () => void;
}

const LogsModal: React.FC<LogsModalProps> = ({ show, onHide }) => {
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (show) {
            fetchLogs();
        }
    }, [show]);

    const fetchLogs = async () => {
        try {
            setLoading(true);
            const response = await axios.get('http://localhost:8000/api/logs');
            setLogs(response.data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Erro ao carregar logs');
        } finally {
            setLoading(false);
        }
    };

    const handleDownload = async () => {
        try {
            const response = await axios.get('http://localhost:8000/api/logs/download', {
                responseType: 'blob'
            });
            
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `logs_${new Date().toISOString().slice(0,19).replace(/[:]/g, '-')}.csv`);
            document.body.appendChild(link);
            link.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(link);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Erro ao baixar logs');
        }
    };

    const getLevelColor = (level: string): string => {
        switch (level.toUpperCase()) {
            case 'ERROR':
                return '#ffebee';
            case 'WARNING':
                return '#fff3e0';
            case 'INFO':
                return '#e3f2fd';
            default:
                return '#ffffff';
        }
    };

    const formatTimestamp = (timestamp: string): string => {
        try {
            // Tenta diferentes formatos de data
            const formats = [
                "yyyy-MM-dd HH:mm:ss,SSS",
                "yyyy-MM-dd HH:mm:ss",
                "yyyy-MM-dd HH:mm",
                "dd/MM/yyyy HH:mm:ss"
            ];

            for (const fmt of formats) {
                try {
                    const date = parse(timestamp, fmt, new Date());
                    return format(date, "dd 'de' MMMM 'de' yyyy 'às' HH:mm:ss", {
                        locale: ptBR
                    });
                } catch {
                    continue;
                }
            }

            // Se nenhum formato funcionou, retorna o timestamp original
            return timestamp;
        } catch (err) {
            console.error('Erro ao formatar timestamp:', err);
            return timestamp;
        }
    };

    return (
        <Modal show={show} onHide={onHide} size="xl">
            <Modal.Header closeButton>
                <Modal.Title>Logs do Sistema</Modal.Title>
                <Button variant="primary" onClick={handleDownload} className="ms-2">
                    Download CSV
                </Button>
            </Modal.Header>
            <Modal.Body>
                {loading ? (
                    <div className="text-center">Carregando logs...</div>
                ) : error ? (
                    <div className="alert alert-danger">{error}</div>
                ) : (
                    <Table striped bordered hover>
                        <thead>
                            <tr>
                                <th>Data/Hora</th>
                                <th>Nível</th>
                                <th>Job ID</th>
                                <th>Mensagem</th>
                            </tr>
                        </thead>
                        <tbody>
                            {logs.map((log, index) => (
                                <tr key={index} style={{ backgroundColor: getLevelColor(log.level) }}>
                                    <td>{formatTimestamp(log.timestamp)}</td>
                                    <td>{log.level}</td>
                                    <td>{log.job_id || '-'}</td>
                                    <td>{log.message}</td>
                                </tr>
                            ))}
                        </tbody>
                    </Table>
                )}
            </Modal.Body>
        </Modal>
    );
};

export default LogsModal; 