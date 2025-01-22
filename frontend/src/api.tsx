import axios from 'axios';
import { Repository, SearchResponse } from './types';

const API_BASE_URL = 'http://localhost:8000';

export const getRepositories = async (): Promise<Repository[]> => {
  const response = await axios.get(`${API_BASE_URL}/repos/list`);
  return response.data;
};

export const searchRepository = async (query: string, owner: string, name: string): Promise<SearchResponse> => {
  const response = await axios.post(`${API_BASE_URL}/search/faiss`, {
    query,
    owner,
    name,
  });
  return response.data;
};

export const initializeRepository = async (owner: string, repo: string): Promise<void> => {
  await axios.post(`${API_BASE_URL}/repos/init`, {
    owner,
    repo,
  });
};