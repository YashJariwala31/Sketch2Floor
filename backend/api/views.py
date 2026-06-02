from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FloorplanJob
from .pipeline import is_floorplan_job_active, seed_demo_job, start_floorplan_job_async
from .serializers import FloorplanJobDetailSerializer, FloorplanJobSerializer
from .services import delete_job_assets, get_job_source_stem, mark_job_queued, scaffold_job_outputs


def get_request_owner_email(request):
    return (request.headers.get('X-User-Email') or '').strip().lower()


class OwnerScopedJobsMixin:
    def require_owner_email(self):
        owner_email = get_request_owner_email(self.request)
        if not owner_email:
            raise ValidationError({'detail': 'Sign in again before accessing floor plan jobs.'})
        return owner_email

    def get_queryset(self):
        return FloorplanJob.objects.filter(owner_email=self.require_owner_email())


class HealthView(APIView):
    def get(self, request):
        return Response({'status': 'ok', 'service': 'sketch2floorplan-backend'})


class FloorplanJobListCreateView(OwnerScopedJobsMixin, generics.ListCreateAPIView):
    serializer_class = FloorplanJobSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        if not request.FILES.get('original_image'):
            return Response({'detail': 'Upload an original image before creating a job.'}, status=400)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        image = self.request.FILES.get('original_image')
        name = serializer.validated_data.get('name') or 'New floorplan job'
        owner_email = self.require_owner_email()
        job = serializer.save(
            name=name,
            owner_email=owner_email,
            status=FloorplanJob.Status.DRAFT,
            original_filename=image.name if image else '',
        )

        if not image:
            return

        scaffold_job_outputs(job, get_job_source_stem(job))
        mark_job_queued(job, 'queued_from_upload')
        start_floorplan_job_async(job.id)


class FloorplanJobDetailView(OwnerScopedJobsMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FloorplanJobDetailSerializer

    def perform_destroy(self, instance):
        delete_job_assets(instance)
        instance.delete()


class FloorplanJobStartView(APIView):
    def post(self, request, pk):
        owner_email = get_request_owner_email(request)
        if not owner_email:
            raise ValidationError({'detail': 'Sign in again before starting a floor plan job.'})

        job = get_object_or_404(FloorplanJob, pk=pk, owner_email=owner_email)
        if not job.original_image:
            return Response({'detail': 'Upload an original image before starting the job.'}, status=400)

        if job.status in {FloorplanJob.Status.QUEUED, FloorplanJob.Status.PROCESSING} and is_floorplan_job_active(job.id):
            serializer = FloorplanJobDetailSerializer(job, context={'request': request})
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)

        scaffold_job_outputs(job, get_job_source_stem(job, f'job_{job.id}'))
        mark_job_queued(job, 'queued_from_api')
        start_floorplan_job_async(job.id)

        serializer = FloorplanJobDetailSerializer(job, context={'request': request})
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class FloorplanJobDemoView(APIView):
    def post(self, request):
        owner_email = get_request_owner_email(request)
        if not owner_email:
            raise ValidationError({'detail': 'Sign in again before creating a demo floor plan job.'})

        name = request.data.get('name') or 'Demo floorplan job'
        job = FloorplanJob.objects.create(
            name=name,
            owner_email=owner_email,
            description='Sample completed job created from the repository demo outputs.',
            status=FloorplanJob.Status.DRAFT,
            original_filename='36.jpeg',
        )
        seed_demo_job(job)
        serializer = FloorplanJobDetailSerializer(job, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
