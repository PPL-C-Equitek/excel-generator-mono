import { fetchAPI } from '@/lib/api';

export interface AboutResponse {
  team: string;
  project: string;
}

export async function getAbout(): Promise<AboutResponse> {
  return fetchAPI('about/');
}