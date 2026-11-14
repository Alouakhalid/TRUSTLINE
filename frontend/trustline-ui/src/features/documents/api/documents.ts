import { api } from '@/shared/lib/api-client';

export async function uploadDocument(file: File, astronautId: string) {
  return api.uploadDocument(file, astronautId);
}
