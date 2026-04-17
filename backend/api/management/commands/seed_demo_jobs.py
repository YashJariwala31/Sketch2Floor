from django.core.management.base import BaseCommand

from api.models import FloorplanJob
from api.pipeline import seed_demo_job


class Command(BaseCommand):
    help = 'Create one or more demo floorplan jobs using the sample outputs already in the repo.'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=1)

    def handle(self, *args, **options):
        count = max(1, int(options['count']))
        for index in range(count):
            job = FloorplanJob.objects.create(
                name=f'Demo floorplan job {index + 1}',
                description='Seeded from repository sample outputs.',
                original_filename='36.jpeg',
            )
            seed_demo_job(job)
            self.stdout.write(self.style.SUCCESS(f'Created demo job #{job.id}'))
