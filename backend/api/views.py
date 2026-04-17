import shutil
from pathlib import Path

from rest_framework import generics
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FloorplanJob
from .pipeline import seed_demo_job, start_floorplan_job_async
from .serializers import FloorplanJobSerializer
from .services import build_expected_output_paths


class HealthView(APIView):
    def get(self, request):
        return Response({'status': 'ok', 'service': 'sketch2floorplan-backend'})


class FloorplanJobListCreateView(generics.ListCreateAPIView):
    queryset = FloorplanJob.objects.all()
    serializer_class = FloorplanJobSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def perform_create(self, serializer):
        image = self.request.FILES.get('original_image')
        name = serializer.validated_data.get('name') or 'New floorplan job'
        job = serializer.save(
            name=name,
            status=FloorplanJob.Status.QUEUED if image else FloorplanJob.Status.DRAFT,
            original_filename=image.name if image else '',
        )

        if image:
            source_stem = Path(image.name).stem
            paths = build_expected_output_paths(job.id, source_stem)
            job.door_mask_path = paths['door_mask_path']
            job.window_mask_path = paths['window_mask_path']
            job.geometry_path = paths['geometry_path']
            job.overlay_path = paths['overlay_path']
            job.combined_overlay_path = paths['combined_overlay_path']
            job.wall_polygons_path = paths['wall_polygons_path']
            job.room_polygons_path = paths['room_polygons_path']
            job.fused_floorplan_path = paths['fused_floorplan_path']
            job.metadata = {
                **job.metadata,
                'pipeline_state': 'scaffolded',
                'source_stem': source_stem,
            }
            job.save(
                update_fields=[
                    'door_mask_path',
                    'window_mask_path',
                    'geometry_path',
                    'overlay_path',
                    'combined_overlay_path',
                    'wall_polygons_path',
                    'room_polygons_path',
                    'fused_floorplan_path',
                    'metadata',
                ]
            )
            job.metadata = {
                **job.metadata,
                'pipeline_state': 'queued_from_upload',
            }
            job.save(update_fields=['metadata', 'updated_at'])
            start_floorplan_job_async(job.id)


class FloorplanJobDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = FloorplanJob.objects.all()
    serializer_class = FloorplanJobSerializer

    def perform_destroy(self, instance):
        if instance.original_image:
            instance.original_image.delete(save=False)

        job_root = Path(instance.combined_overlay_path).parent.parent if instance.combined_overlay_path else None
        if job_root and job_root.exists():
            shutil.rmtree(job_root, ignore_errors=True)

        instance.delete()


class FloorplanJobStartView(APIView):
    def post(self, request, pk):
        job = FloorplanJob.objects.get(pk=pk)
        if not job.original_image:
            return Response({'detail': 'Upload an original image before starting the job.'}, status=400)

        job.status = FloorplanJob.Status.QUEUED
        job.metadata = {
            **job.metadata,
            'pipeline_state': 'queued_from_api',
        }
        job.save(update_fields=['status', 'metadata', 'updated_at'])
        start_floorplan_job_async(job.id)

        serializer = FloorplanJobSerializer(job, context={'request': request})
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class FloorplanJobDemoView(APIView):
    def post(self, request):
        name = request.data.get('name') or 'Demo floorplan job'
        job = FloorplanJob.objects.create(
            name=name,
            description='Sample completed job created from the repository demo outputs.',
            status=FloorplanJob.Status.DRAFT,
            original_filename='36.jpeg',
        )
        seed_demo_job(job)
        serializer = FloorplanJobSerializer(job, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
