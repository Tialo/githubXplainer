export interface Repository {
    owner: string;
    name: string;
  }
  
  export interface SearchResponse {
    summary: string;
    search_time: number;
    load_time: number;
    prompt: string;
  }