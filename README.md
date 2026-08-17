# Coletor de Informações da Máquina - .exe para MongoDB Atlas

Aplicação Python compilada para .exe que coleta informações da máquina e envia para o MongoDB Atlas.

## Estrutura
```
coletor_maquina/
├── main.py           # Código principal
├── config.json       # Configuração do MongoDB (edite antes de rodar)
├── requirements.txt  # Dependências Python
├── build.bat         # Script de build para Windows
└── dist/             # Gerado após build (contém .exe)
```

## Informações Coletadas
- **OS**: Sistema, versão, arquitetura, hostname
- **CPU**: Cores físicos/lógicos, frequência, nome
- **RAM**: Total, slots, frequência, tipo
- **Disco**: Modelos dos discos e capacidade
- **Rede**: IP, MAC, hostname
- **Hardware (via WMI)**: BIOS, placa-mãe, marca/modelo, número de série, GPU, monitor
- **Timestamp**: Data/hora da coleta

## Como Usar

### 1. Configurar o MongoDB Atlas
Edite `config.json`:
```json
{
  "mongodb_uri": "mongodb+srv://USUARIO:SENHA@cluster0.xxxxx.mongodb.net/?appName=Cluster0",
  "database": "ccsoftware",
  "collection": "ativos",
  "timeout_ms": 30000
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

## Documento Salvo no MongoDB
Cada execução insere um documento na coleção configurada, por exemplo:
```json
{
  "so": "Windows 10 Build 10.0.19045",
  "hostname": "F2430-CAIXA",
  "ip": "192.168.1.78",
  "mac": "00:15:5D:6D:FB:A9",
  "processador": "Intel(R) Pentium(R) CPU G4560 @ 3.50GHz",
  "ram": "8 GB",
  "armazenamento": "Hitachi HDS5C1050CLA382 (465 GB Fixed hard disk media)",
  "...": "...",
  "collected_at": "2026-08-12T19:49:27.205698"
}
```

## Requisitos
- Python 3.8+
- PyInstaller (`pip install pyinstaller`)
- Windows (para gerar .exe nativo)
- Conexão com a internet e acesso aos nós do cluster (porta 27017)

## Dependências
- `psutil` - Informações do sistema
- `wmi` - Informações detalhadas de hardware
- `pymongo` - Cliente MongoDB
- `dnspython` - Suporte ao prefixo `mongodb+srv://`

## Observação
O arquivo `config.json` contém credenciais de acesso e está no `.gitignore` para não ser versionado.
