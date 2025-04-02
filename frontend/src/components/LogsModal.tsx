import React, { useEffect, useState } from 'react';
import { Modal, Table, Button } from 'react-bootstrap';
import axios from 'axios';

interface LogFile {
    nome: string;
    data_criacao: string;
    tamanho: number;
    caminho: string;
}

interface LogsModalProps {
    show: boolean;
    onHide: () => void;
}

const LogsModal: React.FC<LogsModalProps> = ({ show, onHide }) => {
    const [logs, setLogs] = useState<LogFile[]>([]);
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
            setError(null);
        } catch (err) {
            setError('Erro ao carregar logs do terminal');
            console.error('Erro ao carregar logs:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleDownload = async (filename: string) => {
        try {
            const response = await axios.get(`http://localhost:8000/api/logs/download/${filename}`, {
                responseType: 'blob'
            });
            
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', filename);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (err) {
            console.error('Erro ao baixar log:', err);
        }
    };

    return (
        <Modal show={show} onHide={onHide} size="xl">
            <Modal.Header closeButton>
                <Modal.Title>Logs do Terminal</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {loading ? (
                    <div className="text-center">Carregando logs do terminal...</div>
                ) : error ? (
                    <div className="alert alert-danger">{error}</div>
                ) : (
                    <Table striped bordered hover>
                        <thead>
                            <tr>
                                <th>Data/Hora</th>
                                <th>Arquivo de Log</th>
                                <th>Tamanho</th>
                                <th>Ações</th>
                            </tr>
                        </thead>
                        <tbody>
                            {logs.map((log, index) => (
                                <tr key={index}>
                                    <td>{new Date(log.data_criacao).toLocaleString('pt-BR')}</td>
                                    <td>{log.nome}</td>
                                    <td>{(log.tamanho / 1024).toFixed(2)} KB</td>
                                    <td>
                                        <Button
                                            variant="primary"
                                            size="sm"
                                            onClick={() => handleDownload(log.nome)}
                                        >
                                            Download
                                        </Button>
                                    </td>
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