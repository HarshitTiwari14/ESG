"""
Seed realistic demo data for Breathe ESG.

SAP data: Based on MB51 (material document list) flat-file export format.
  MB51 is SAP's standard goods movement report. Sustainability teams typically
  request this from their SAP team filtered by movement type 201 (goods issue
  to cost center) or material groups covering fuel. The export is semicolon-delimited
  with German column headers in some SAP versions.

Utility data: Based on Indian DISCOM portal CSV exports (e.g., BSES, TPDDL, Adani).
  Most portals let you export billing history as CSV with columns: Account No.,
  Billing Period, Units Consumed (kWh), Amount. We add meter ID and tariff info
  typical of commercial accounts.

Travel data: Based on Navan (formerly TripActions) "Trip Report" CSV export and
  Concur "Standard Detail" report. Common columns: traveler name, trip date, type
  (Air/Hotel/Car), origin, destination, cabin class, amount.
"""
import io
import csv
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Organisation
from ingestion.services import ingest_file
from ingestion.models import IngestionBatch

User = get_user_model()

SAP_DATA = """Belnr;Bldat;Budat;Werks;Kostl;Matnr;Maktx;Menge;Meins;Lifnr;Name1;Netwr;Waers
5000012301;15.01.2024;15.01.2024;IN01;CC-PROD-01;MAT-HSD-001;High Speed Diesel;12500;L;VND-001;Bharat Petroleum;875000;INR
5000012302;22.01.2024;22.01.2024;IN01;CC-PROD-01;MAT-HSD-001;High Speed Diesel;8900;L;VND-001;Bharat Petroleum;623000;INR
5000012303;05.02.2024;05.02.2024;IN02;CC-MAINT-01;MAT-HSD-001;High Speed Diesel;3200;L;VND-002;Indian Oil Corporation;224000;INR
5000012304;14.02.2024;14.02.2024;IN01;CC-PROD-01;MAT-PET-001;Petrol MS;1800;L;VND-003;HP Fuels;130000;INR
5000012305;28.02.2024;28.02.2024;IN03;CC-GEN-01;MAT-HSD-001;High Speed Diesel;25000;L;VND-001;Bharat Petroleum;1750000;INR
5000012306;10.03.2024;10.03.2024;IN01;CC-PROD-01;MAT-CNG-001;Compressed Natural Gas;4500;kwh;VND-004;IGL Limited;180000;INR
5000012307;18.03.2024;18.03.2024;IN02;CC-MAINT-01;MAT-HSD-001;High Speed Diesel;6700;L;VND-001;Bharat Petroleum;469000;INR
5000012308;25.03.2024;25.03.2024;IN01;CC-PROD-02;MAT-HSD-001;High Speed Diesel;9100;L;VND-002;Indian Oil Corporation;637000;INR
5000012309;02.04.2024;02.04.2024;IN03;CC-GEN-01;MAT-PET-001;Petrol MS;2300;L;VND-003;HP Fuels;166000;INR
5000012310;15.04.2024;15.04.2024;IN01;CC-PROD-01;MAT-HSD-001;High Speed Diesel;11200;L;VND-001;Bharat Petroleum;784000;INR
5000012311;22.04.2024;22.04.2024;IN02;CC-MAINT-01;MAT-CNG-001;Compressed Natural Gas;3800;kwh;VND-004;IGL Limited;152000;INR
5000012312;30.04.2024;30.04.2024;IN01;CC-PROD-01;MAT-HSD-001;High Speed Diesel;14500;L;VND-001;Bharat Petroleum;1015000;INR
"""

UTILITY_DATA = """Meter ID,Site,Billing Period Start,Billing Period End,Consumption,Unit,Tariff,Grid Region,Amount,Currency
MTR-BLR-001,Bangalore Office,01/01/2024,31/01/2024,48500,kWh,Commercial HT,India,387000,INR
MTR-BLR-002,Bangalore Warehouse,01/01/2024,31/01/2024,22100,kWh,Commercial LT,India,176800,INR
MTR-DEL-001,Delhi HQ,01/01/2024,31/01/2024,61200,kWh,Commercial HT,India,489600,INR
MTR-BLR-001,Bangalore Office,01/02/2024,29/02/2024,51300,kWh,Commercial HT,India,410400,INR
MTR-BLR-002,Bangalore Warehouse,01/02/2024,29/02/2024,19800,kWh,Commercial LT,India,158400,INR
MTR-DEL-001,Delhi HQ,01/02/2024,29/02/2024,63800,kWh,Commercial HT,India,510400,INR
MTR-MUM-001,Mumbai Branch,01/02/2024,29/02/2024,28900,kWh,Commercial LT,India,231200,INR
MTR-BLR-001,Bangalore Office,01/03/2024,31/03/2024,55600,kWh,Commercial HT,India,444800,INR
MTR-BLR-002,Bangalore Warehouse,01/03/2024,31/03/2024,24200,kWh,Commercial LT,India,193600,INR
MTR-DEL-001,Delhi HQ,01/03/2024,31/03/2024,67100,kWh,Commercial HT,India,536800,INR
MTR-MUM-001,Mumbai Branch,01/03/2024,31/03/2024,31200,kWh,Commercial LT,India,249600,INR
MTR-DEL-001,Delhi HQ,01/04/2024,30/04/2024,72400,kWh,Commercial HT,India,579200,INR
"""

TRAVEL_DATA = """Trip Date,Traveler,Travel Type,Origin,Destination,Class,Distance (km),Hotel Name,Nights,Amount,Currency,Cost Center
2024-01-10,EMP001,Flight,DEL,BLR,economy,,,,18500,INR,CC-SALES
2024-01-10,EMP001,Hotel,,,,,The Leela Palace Bangalore,,5,52000,INR,CC-SALES
2024-01-15,EMP002,Flight,BOM,DEL,business,,,,35000,INR,CC-EXEC
2024-01-18,EMP003,Flight,DEL,JFK,economy,,,,85000,INR,CC-BD
2024-01-25,EMP004,Flight,BLR,DXB,economy,,,,32000,INR,CC-OPS
2024-01-25,EMP004,Hotel,,,,,Marriott Dubai,,3,28000,INR,CC-OPS
2024-02-03,EMP002,Flight,DEL,LHR,business,,,,95000,INR,CC-EXEC
2024-02-03,EMP002,Hotel,,,,,The Ritz London,,4,120000,INR,CC-EXEC
2024-02-08,EMP005,Taxi,DEL,DEL,,45,,,1800,INR,CC-SALES
2024-02-12,EMP001,Flight,BLR,BOM,economy,,,,9500,INR,CC-SALES
2024-02-15,EMP006,Train,DEL,AGR,,200,,,1200,INR,CC-OPS
2024-02-20,EMP003,Flight,JFK,DEL,economy,,,,82000,INR,CC-BD
2024-03-01,EMP007,Flight,DEL,SIN,economy,,,,42000,INR,CC-TECH
2024-03-01,EMP007,Hotel,,,,,Raffles Hotel Singapore,,5,85000,INR,CC-TECH
2024-03-10,EMP002,Flight,DEL,BOM,business,,,,28000,INR,CC-EXEC
2024-03-15,EMP008,Car Rental,BLR,,,350,,,12000,INR,CC-SALES
2024-03-22,EMP001,Flight,BOM,HYD,economy,,,,7500,INR,CC-SALES
2024-04-05,EMP004,Flight,DXB,BLR,economy,,,,29000,INR,CC-OPS
2024-04-12,EMP009,Flight,DEL,CDG,economy,,,,75000,INR,CC-BD
2024-04-12,EMP009,Hotel,,,,,Sofitel Paris,,6,95000,INR,CC-BD
"""


class Command(BaseCommand):
    help = 'Seed demo organisations, users, and emission data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding demo data...')

        # Create org
        org, _ = Organisation.objects.get_or_create(
            slug='acme-corp',
            defaults={'name': 'ACME Manufacturing Ltd.', 'reporting_year_start': '01-01'}
        )

        # Create analyst user
        analyst, created = User.objects.get_or_create(
            username='analyst',
            defaults={
                'email': 'analyst@acme.com',
                'first_name': 'Priya',
                'last_name': 'Sharma',
                'organisation': org,
                'role': 'analyst',
            }
        )
        if created:
            analyst.set_password('demo1234')
            analyst.save()

        # Create admin user
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@acme.com',
                'first_name': 'Rahul',
                'last_name': 'Verma',
                'organisation': org,
                'role': 'admin',
                'is_staff': True,
            }
        )
        if created:
            admin_user.set_password('demo1234')
            admin_user.save()

        # Ingest SAP data
        sap_file = io.BytesIO(SAP_DATA.encode('utf-8'))
        sap_file.name = 'sap_mb51_fuel_Q1_2024.csv'
        batch = ingest_file(sap_file, IngestionBatch.SOURCE_SAP, org, analyst, 'sap_mb51_fuel_Q1_2024.csv')
        self.stdout.write(f'  SAP batch {batch.id}: {batch.row_count} records, {batch.error_count} errors')

        # Ingest utility data
        util_file = io.BytesIO(UTILITY_DATA.encode('utf-8'))
        batch = ingest_file(util_file, IngestionBatch.SOURCE_UTILITY, org, analyst, 'utility_portal_Q1_2024.csv')
        self.stdout.write(f'  Utility batch {batch.id}: {batch.row_count} records, {batch.error_count} errors')

        # Ingest travel data
        travel_file = io.BytesIO(TRAVEL_DATA.encode('utf-8'))
        batch = ingest_file(travel_file, IngestionBatch.SOURCE_TRAVEL, org, analyst, 'navan_trip_report_Q1_2024.csv')
        self.stdout.write(f'  Travel batch {batch.id}: {batch.row_count} records, {batch.error_count} errors')

        self.stdout.write(self.style.SUCCESS(
            '\nDemo data seeded!\n'
            'Login: analyst / demo1234\n'
            f'Org: {org.name}'
        ))
