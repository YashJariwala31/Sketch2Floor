from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FloorplanJob
from .pipeline import is_floorplan_job_active, seed_demo_job, start_floorplan_job_async
from .serializers import FloorplanJobSerializer
from .services import delete_job_assets, get_source_stem, mark_job_queued, scaffold_job_outputs


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
            status=FloorplanJob.Status.DRAFT,
            original_filename=image.name if image else '',
        )

        if not image:
            return

        scaffold_job_outputs(job, get_source_stem(image.name))
        mark_job_queued(job, 'queued_from_upload')
        start_floorplan_job_async(job.id)


class FloorplanJobDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = FloorplanJob.objects.all()
    serializer_class = FloorplanJobSerializer

    def perform_destroy(self, instance):
        delete_job_assets(instance)
        instance.delete()


class FloorplanJobStartView(APIView):
    def post(self, request, pk):
        job = get_object_or_404(FloorplanJob, pk=pk)
        if not job.original_image:
            return Response({'detail': 'Upload an original image before starting the job.'}, status=400)

        if job.status in {FloorplanJob.Status.QUEUED, FloorplanJob.Status.PROCESSING} and is_floorplan_job_active(job.id):
            serializer = FloorplanJobSerializer(job, context={'request': request})
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)

        scaffold_job_outputs(job, job.metadata.get('source_stem') or get_source_stem(job.original_filename, f'job_{job.id}'))
        mark_job_queued(job, 'queued_from_api')
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
