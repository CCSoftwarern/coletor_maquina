# Coletor de Informações da Máquina - .exe para Xano

Aplicação Python compilada para .exe que coleta informações da máquina e envia para API Xano.

## Estrutura
```
coletor_maquina/
├── main.py           # Código principal
├── config.json       # Configuração da API (edite antes de rodar)
├── requirements.txt  # Dependências Python
├── build.bat         # Script de build para Windows
└── dist/             # Gerado após build (contém .exe)
```

## Informações Coletadas
- **OS**: Sistema, versão, arquitetura, hostname
- **CPU**: Cores físicos/lógicos, frequência, uso %
- **RAM**: Total, disponível, usada, % uso
- **Disco**: Total, usado, livre, % uso (unidade do sistema)
- **Rede**: IP, MAC, hostname
- **Timestamp**: Data/hora da coleta

## Como Usar

### 1. Configurar a API
Edite `config.json`:
```json
{
  "api_base_url": "https://SEU_WORKSPACE.xano.io/api:SEU_API_GROUP",
  "endpoint": "/ativos",
  "auth_header": "Authorization",
  "auth_value": "Bearer SEU_TOKEN_AQUI",
  "specs_field": "specs",
  "timeout_seconds": 30
}
```

### 2. Build do .exe
```cmd
cd coletor_maquina
build.bat
```

### 3. Testar
```cmd
cd dist
copy ..\config.json .
:: Edite config.json com suas credenciais reais
coletor_maquina.exe
```

## Payload Enviado para Xano
```json
{
  "specs": {
    "os": {...},
    "cpu": {...},
    "memory": {...},
    "disk": {...},
    "network": {...},
    "collected_at": "2024-01-15T10:30:00.000000"
  }
}
```

O campo `specs` (configurável em `specs_field`) recebe o JSON completo das informações da máquina.

## Requisitos
- Python 3.8+
- PyInstaller (`pip install pyinstaller`)
- Windows (para gerar .exe nativo)

## Dependências
- `psutil` - Informações do sistema
- `requests` - HTTP client