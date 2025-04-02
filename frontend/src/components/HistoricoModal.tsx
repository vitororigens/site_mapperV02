import React, { useEffect, useState } from 'react';
import { Modal, Table, Button } from 'react-bootstrap';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

interface ArquivoXLSX {
    nome: string;
    data_criacao: string;
    tamanho: number;
    caminho: string;
}

interface HistoricoModalProps {
    show: boolean;
    onHide: () => void;
}

const HistoricoModal: React.FC<HistoricoModalProps> = ({ show, onHide }) => {
    const [arquivos, setArquivos] = useState<ArquivoXLSX[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (show) {
            fetchArquivos();
        }
    }, [show]);

    const fetchArquivos = async () => {
        try {
            setLoading(true);
            const response = await fetch('http://localhost:8000/api/historico');
            if (!response.ok) {
                throw new Error('Erro ao carregar histórico');
            }
            const data = await response.json();
            setArquivos(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Erro ao carregar histórico');
        } finally {
            setLoading(false);
        }
    };

    const handleDownload = async (nomeArquivo: string) => {
        try {
            const response = await fetch(`http://localhost:8000/api/historico/download/${nomeArquivo}`);
            if (!response.ok) {
                throw new Error('Erro ao baixar arquivo');
            }
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = nomeArquivo;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Erro ao baixar arquivo');
        }
    };

    const formatarTamanho = (bytes: number): string => {
        const unidades = ['B', 'KB', 'MB', 'GB'];
        let tamanho = bytes;
        let unidadeIndex = 0;
        
        while (tamanho >= 1024 && unidadeIndex < unidades.length - 1) {
            tamanho /= 1024;
            unidadeIndex++;
        }
        
        return `${tamanho.toFixed(2)} ${unidades[unidadeIndex]}`;
    };

    return (
        <Modal show={show} onHide={onHide} size="lg">
            <Modal.Header closeButton>
                <Modal.Title>Histórico de Arquivos</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {loading ? (
                    <div className="text-center">Carregando...</div>
                ) : error ? (
                    <div className="alert alert-danger">{error}</div>
                ) : (
                    <Table striped bordered hover>
                        <thead>
                            <tr>
                                <th>Nome do Arquivo</th>
                                <th>Data de Criação</th>
                                <th>Tamanho</th>
                                <th>Ações</th>
                            </tr>
                        </thead>
                        <tbody>
                            {arquivos.map((arquivo) => (
                                <tr key={arquivo.caminho}>
                                    <td>{arquivo.nome}</td>
                                    <td>
                                        {format(new Date(arquivo.data_criacao), "dd 'de' MMMM 'de' yyyy 'às' HH:mm", {
                                            locale: ptBR
                                        })}
                                    </td>
                                    <td>{formatarTamanho(arquivo.tamanho)}</td>
                                    <td>
                                        <Button
                                            variant="primary"
                                            size="sm"
                                            onClick={() => handleDownload(arquivo.nome)}
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

export default HistoricoModal; 