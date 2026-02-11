import { fetchAPI } from "@/lib/api";

export interface Member {
  npm: string;
  name: string;
}

export interface MembersResponse {
  group: string;
  members: Member[];
}

export async function getMembers(): Promise<MembersResponse> {
  return fetchAPI("members/");
}
