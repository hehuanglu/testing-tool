function lookups(repo, wrapper, id, principal, guard) {
  // ruleid: nestjs-ownership-id-only-find-one
  repo.findOneBy({ id });
  // ruleid: nestjs-ownership-id-only-find-one, nestjs-ownership-additional-criteria-review
  repo.findOneBy({ id, ownerId: principal.id });
  // ruleid: nestjs-ownership-id-only-find-one, nestjs-ownership-additional-criteria-review
  repo.findOne({ where: { id, status: 'active' } });
  guard(principal, id); // Prior guard does not remove an inventory candidate.
  // ruleid: nestjs-ownership-id-only-find-one
  repo.findOne({ where: { id } });
  // ok: nestjs-ownership-id-only-find-one, nestjs-ownership-additional-criteria-review
  wrapper.loadForActor(principal, id); // Different shape; inspect wrapper manually.
  // ok: nestjs-ownership-id-only-find-one, nestjs-ownership-additional-criteria-review
  repo.findOneBy({ slug: 'public-doc' });
}
