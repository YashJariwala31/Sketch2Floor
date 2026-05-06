import { useEffect, useState } from 'react';

import { createJobWithImage, deleteJob, fetchJobs, startJob, testBackendConnection } from '../api/client';
import { saveImageToDevice } from '../utils/saveImageToDevice';

const POLLABLE_STATUSES = new Set(['queued', 'processing']);

export function useFloorplanJobs({ enabled, albumName = 'Sketch2FloorPlan' }) {
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [connection, setConnection] = useState(null);

  async function refreshConnection() {
    const result = await testBackendConnection();
    setConnection(result);

    if (!result.ok) {
      setError(result.error || 'Unable to reach backend');
    } else {
      setError('');
    }

    return result;
  }

  async function loadJobs({ showLoading = true } = {}) {
    if (!enabled) {
      return [];
    }

    try {
      if (showLoading) {
        setLoading(true);
      }

      const [data, connectionResult] = await Promise.all([fetchJobs(), refreshConnection()]);
      const nextJobs = Array.isArray(data) ? data : [];
      setJobs(nextJobs);
      setSelectedJob((currentJob) => (currentJob ? nextJobs.find((item) => item.id === currentJob.id) || null : null));

      if (connectionResult.ok) {
        setError('');
      }

      return nextJobs;
    } catch (err) {
      setError(err.message || 'Unable to reach backend');
      throw err;
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  }

  function clearSelectedJob() {
    setSelectedJob(null);
  }

  useEffect(() => {
    if (enabled) {
      loadJobs().catch(() => undefined);
      return;
    }

    setJobs([]);
    setSelectedJob(null);
    setLoading(false);
    setBusy(false);
    setError('');
    setConnection(null);
  }, [enabled]);

  useEffect(() => {
    if (!enabled || !selectedJob || !POLLABLE_STATUSES.has(selectedJob.status)) {
      return undefined;
    }

    const intervalId = setInterval(() => {
      loadJobs({ showLoading: false }).catch(() => undefined);
    }, 4000);

    return () => clearInterval(intervalId);
  }, [enabled, selectedJob?.id, selectedJob?.status]);

  async function uploadAsset({ asset, name, description, fallbackName, failureMessage }) {
    try {
      setBusy(true);
      setError('');

      const created = await createJobWithImage({
        name,
        description,
        imageUri: asset.uri,
        imageName: asset.fileName || fallbackName,
        mimeType: asset.mimeType || 'image/jpeg',
      });

      setSelectedJob(created);
      await loadJobs({ showLoading: false });
      return created;
    } catch (err) {
      const parsed = err.message || failureMessage || 'Unable to upload image';
      setError(parsed);
      throw new Error(parsed);
    } finally {
      setBusy(false);
    }
  }

  async function startExistingJob(job) {
    if (!job) {
      return null;
    }

    try {
      setBusy(true);
      setError('');
      const startedJob = await startJob(job.id);
      setSelectedJob(startedJob);
      await loadJobs({ showLoading: false });
      return startedJob;
    } catch (err) {
      const parsed = err.message || 'Unable to start job';
      setError(parsed);
      throw new Error(parsed);
    } finally {
      setBusy(false);
    }
  }

  async function deleteExistingJob(job) {
    if (!job) {
      return false;
    }

    try {
      setBusy(true);
      setError('');
      await deleteJob(job.id);
      setSelectedJob((currentJob) => (currentJob?.id === job.id ? null : currentJob));
      await loadJobs({ showLoading: false });
      return true;
    } catch (err) {
      const parsed = err.message || 'Unable to delete job';
      setError(parsed);
      throw new Error(parsed);
    } finally {
      setBusy(false);
    }
  }

  async function saveResult(url) {
    if (!url) {
      throw new Error('No generated floor plan available yet.');
    }

    try {
      setBusy(true);
      setError('');
      await saveImageToDevice(url, albumName);
      return true;
    } catch (err) {
      const parsed = err.message || 'Unable to prepare download';
      setError(parsed);
      throw new Error(parsed);
    } finally {
      setBusy(false);
    }
  }

  return {
    jobs,
    selectedJob,
    setSelectedJob,
    clearSelectedJob,
    loading,
    busy,
    error,
    setError,
    connection,
    refreshConnection,
    loadJobs,
    uploadAsset,
    startExistingJob,
    deleteExistingJob,
    saveResult,
  };
}
