import { useQuery } from '@tanstack/react-query';
import { projectService } from '../services/projectService';

export function useProjectId() {
  const { data: projects } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectService.getProjects(),
    staleTime: 1000 * 60 * 10,
  });
  return projects?.[0]?._id ?? null;
}
