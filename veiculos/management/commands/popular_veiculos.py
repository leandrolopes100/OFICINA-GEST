from django.core.management.base import BaseCommand
from veiculos.models import Marca, Modelo

# Apenas marcas e modelos comercializados no Brasil
MARCAS_MODELOS = {
    'Chevrolet': [
        'Agile', 'Astra', 'Blazer', 'Camaro', 'Captiva', 'Celta',
        'Classic', 'Cobalt', 'Corsa', 'Corsa Hatch', 'Corsa Sedan',
        'Cruze', 'Cruze Sport6', 'Equinox', 'Joy', 'Meriva', 'Montana',
        'Onix', 'Onix Plus', 'Onix Hatch', 'Prisma', 'S10', 'Silverado',
        'Spin', 'Tracker', 'Trailblazer', 'Vectra', 'Zafira',
    ],
    'Volkswagen': [
        'Amarok', 'Bora', 'Fox', 'Fusca', 'Gol', 'Golf', 'Golf GTI',
        'Jetta', 'Kombi', 'Parati', 'Passat', 'Polo', 'Polo Sedan',
        'Saveiro', 'SpaceCross', 'SpaceFox', 'T-Cross', 'Taos',
        'Tiguan', 'Up', 'Virtus', 'Voyage',
    ],
    'Fiat': [
        'Argo', 'Brava', 'Bravo', 'Cronos', 'Doblo', 'Ducato',
        'Fastback', 'Fiorino', 'Idea', 'Linea', 'Marea', 'Mobi',
        'Palio', 'Palio Weekend', 'Pulse', 'Punto', 'Siena', 'Stilo',
        'Strada', 'Tempra', 'Tipo', 'Toro', 'Uno',
    ],
    'Ford': [
        'Bronco Sport', 'Courier', 'EcoSport', 'Edge', 'Explorer',
        'F-250', 'F-350', 'Fiesta', 'Fiesta Sedan', 'Focus',
        'Focus Sedan', 'Fusion', 'Ka', 'Ka Sedan', 'Maverick',
        'Mustang', 'Ranger', 'Territory', 'Transit',
    ],
    'Toyota': [
        'Bandeirante', 'Camry', 'Corolla', 'Corolla Cross', 'Etios',
        'Etios Sedan', 'Fielder', 'Hilux', 'Hilux SW4', 'Land Cruiser',
        'Prado', 'Prius', 'RAV4', 'Yaris', 'Yaris Sedan',
    ],
    'Honda': [
        'Accord', 'City', 'City Hatch', 'Civic', 'CR-V', 'Fit',
        'HR-V', 'Odyssey', 'WR-V',
    ],
    'Hyundai': [
        'Azera', 'Creta', 'Elantra', 'HB20', 'HB20S', 'HB20X',
        'i30', 'Ioniq 5', 'ix35', 'Sonata', 'Tucson', 'Veloster',
    ],
    'Renault': [
        'Captur', 'Clio', 'Duster', 'Fluence', 'Kangoo', 'Kwid',
        'Logan', 'Master', 'Megane', 'Oroch', 'Sandero',
        'Sandero Stepway', 'Scenic', 'Symbol',
    ],
    'Jeep': [
        'Commander', 'Compass', 'Grand Cherokee', 'Renegade', 'Wrangler',
    ],
    'Nissan': [
        'Frontier', 'Kicks', 'Leaf', 'Livina', 'March', 'Sentra',
        'Tiida', 'Versa', 'X-Trail',
    ],
    'Peugeot': [
        '2008', '206', '207', '207 SW', '208', '3008', '307',
        '308', '408', '5008', 'Expert', 'Partner',
    ],
    'Citroën': [
        'Berlingo', 'C3', 'C4', 'C4 Cactus', 'C4 Lounge', 'C5 Aircross',
        'Jumper', 'Xsara', 'Xsara Picasso',
    ],
    'Mitsubishi': [
        'ASX', 'Eclipse Cross', 'Galant', 'L200 Triton', 'Lancer',
        'Outlander', 'Pajero', 'Pajero Full', 'Pajero Sport',
    ],
    'Kia': [
        'Carnival', 'Cerato', 'EV6', 'Picanto', 'Rio', 'Seltos',
        'Sorento', 'Soul', 'Sportage', 'Stinger', 'Stonic',
    ],
    'Subaru': [
        'BRZ', 'Forester', 'Impreza', 'Legacy', 'Outback', 'WRX',
        'WRX STI', 'XV',
    ],
    'BMW': [
        '118i', '120i', '218i', '320i', '328i', '330i', '420i', '430i',
        '520i', '528i', '530i', '630i', '730i', 'M3', 'M4', 'M5',
        'X1', 'X2', 'X3', 'X4', 'X5', 'X6', 'X7', 'Z3', 'Z4',
    ],
    'Mercedes-Benz': [
        'A 200', 'A 250', 'B 200', 'C 180', 'C 200', 'C 250', 'C 300',
        'CLA 200', 'E 200', 'E 250', 'E 300', 'GLA 200', 'GLA 250',
        'GLB 200', 'GLC 300', 'GLE 400', 'S 400', 'S 500', 'Sprinter',
        'AMG A 45', 'AMG C 63', 'AMG E 63',
    ],
    'Audi': [
        'A1', 'A3', 'A3 Sedan', 'A4', 'A5', 'A6', 'A7', 'A8',
        'Q2', 'Q3', 'Q5', 'Q7', 'Q8', 'RS3', 'RS5', 'S3', 'S4',
        'S5', 'TT', 'e-tron',
    ],
    'Volvo': [
        'C30', 'S40', 'S60', 'S80', 'S90', 'V40', 'V60', 'V90',
        'XC40', 'XC60', 'XC90',
    ],
    'Land Rover': [
        'Defender', 'Discovery', 'Discovery Sport', 'Freelander',
        'Range Rover', 'Range Rover Evoque', 'Range Rover Sport',
        'Range Rover Velar',
    ],
    'Porsche': [
        '718 Boxster', '718 Cayman', '911', 'Cayenne', 'Macan', 'Panamera',
    ],
    'Jaguar': [
        'E-Pace', 'F-Pace', 'F-Type', 'I-Pace', 'XE', 'XF', 'XJ',
    ],
    'Suzuki': [
        'Grand Vitara', 'Jimny', 'Swift', 'Vitara', 'S-Cross',
    ],
    'Chery': [
        'Arrizo 6', 'QQ', 'Tiggo 2', 'Tiggo 3x', 'Tiggo 5x',
        'Tiggo 7', 'Tiggo 8',
    ],
    'Caoa Chery': [
        'Tiggo 2 Pro', 'Tiggo 5x Pro', 'Tiggo 7 Pro', 'Tiggo 8 Pro',
        'Tiggo 8 Pro HEV',
    ],
    'BYD': [
        'Atto 3', 'Dolphin', 'Han', 'King', 'Sea Lion 6', 'Seal',
        'Song Plus', 'Song Plus DM-i', 'Tang',
    ],
    'GWM': [
        'Haval H6', 'Haval H2', 'Jolion', 'Ora 03', 'Poer',
        'Tank 300',
    ],
    'RAM': [
        '700', '1500', '2500', '3500', 'ProMaster',
    ],
    'Dodge': [
        'Challenger', 'Charger', 'Durango', 'Journey',
    ],
    'Iveco': [
        'Daily 30S', 'Daily 35S', 'Daily 55C', 'Daily 70C',
        'Tector', 'Stralis', 'Hi-Way', 'S-Way',
    ],
    'Scania': [
        'G 360', 'G 400', 'G 440', 'P 250', 'P 310', 'P 360',
        'R 440', 'R 500', 'R 560', 'S 500', 'S 560', 'XT',
    ],
    'Volvo Caminhões': [
        'FH 400', 'FH 440', 'FH 460', 'FM 330', 'FM 370',
        'FMX 420', 'VM 270', 'VM 330',
    ],
    'Mercedes-Benz Caminhões': [
        'Accelo 815', 'Accelo 1016', 'Atego 1419', 'Atego 1719',
        'Atego 2425', 'Axor 1933', 'Axor 2535', 'Actros 2646',
        'Actros 2651',
    ],
    'MAN': [
        'TGX 29.440', 'TGX 33.440', 'TGS 24.280', 'TGS 26.280',
        'TGM 15.250', 'TGL 11.180',
    ],
    'Agrale': [
        'Marrua', 'Furgovan', 'MT 12000', 'A 10000',
    ],
    'Troller': [
        'T4',
    ],
}


class Command(BaseCommand):
    help = 'Popula o banco com marcas e modelos de veículos do mercado brasileiro'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpar',
            action='store_true',
            help='Remove todas as marcas e modelos antes de inserir',
        )

    def handle(self, *args, **options):
        if options['limpar']:
            Modelo.objects.all().delete()
            Marca.objects.all().delete()
            self.stdout.write(self.style.WARNING('Marcas e modelos removidos.'))

        total_marcas = 0
        total_modelos = 0

        for nome_marca, modelos in MARCAS_MODELOS.items():
            marca, criada = Marca.objects.get_or_create(nome=nome_marca)
            if criada:
                total_marcas += 1
                self.stdout.write(f'  + Marca: {nome_marca}')

            for nome_modelo in modelos:
                _, criado = Modelo.objects.get_or_create(marca=marca, nome=nome_modelo)
                if criado:
                    total_modelos += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nConcluído! {total_marcas} marca(s) e {total_modelos} modelo(s) inseridos.'
        ))
