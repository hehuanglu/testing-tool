import { Repository, EntityManager } from 'typeorm';
function mutate(map: Map<string, object>, set: Set<string>, service, repo: Repository<any>, manager: EntityManager, id, dto) {
  // ruleid: nestjs-ownership-scalar-mutation-review
  map.delete(id); // Actual receiver is not persistence.
  // ruleid: nestjs-ownership-scalar-mutation-review
  set.delete(id);
  // ruleid: nestjs-ownership-scalar-mutation-review, nestjs-ownership-dto-spread-persistence-review
  service.update(id, dto); // Wrapper may persist; inspect implementation.
  // ruleid: nestjs-ownership-scalar-mutation-review, nestjs-ownership-dto-spread-persistence-review
  repo.update(id, dto);
  // ruleid: nestjs-ownership-scalar-mutation-review
  repo.delete(id);
  // ruleid: nestjs-ownership-scalar-mutation-review, nestjs-ownership-dto-spread-persistence-review
  manager.update('Record', id, dto);
  // ruleid: nestjs-ownership-scalar-mutation-review
  manager.delete('Record', id);
  const receiver = repo;
  // ruleid: nestjs-ownership-scalar-mutation-review, nestjs-ownership-dto-spread-persistence-review
  receiver.update(id, dto);
  // ok: nestjs-ownership-scalar-mutation-review
  service.notify('finished');
}
