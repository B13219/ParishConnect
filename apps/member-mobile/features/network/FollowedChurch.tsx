import { ChurchCard } from "../../components/ChurchCard";
import { Action, Body, Card, Loading, Notice } from "../../components/ui";
import { useServices } from "../../providers/SessionProvider";
import { useNetwork } from "../../providers/NetworkProvider";
import { useLoad } from "../../hooks/useLoad";
import { ApiError } from "../../services/api";
export default function FollowedChurch({ id }: { id: string }) {
  const services = useServices();
  const { controller } = useNetwork();
  const result = useLoad(id, async () => {
    try {
      return await services.church(id);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  });
  return (
    <>
      {result.loading ? <Loading /> : null}
      {result.data ? (
        <ChurchCard church={result.data} />
      ) : result.data === null ? (
        <Card>
          <Body>This church’s public profile is currently unavailable.</Body>
        </Card>
      ) : null}
      <Notice message={result.error} />
      <Action
        secondary
        title="Unfollow"
        run={async () => {
          await services.follow(id, false);
          await controller.refresh();
        }}
      />
    </>
  );
}
