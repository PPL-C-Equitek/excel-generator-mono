import { fetchAPI } from '@/lib/api';

export async function getHealth() {
  return fetchAPI('health/');
}