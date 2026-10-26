// Synthetic matcher fixtures, no real authorization implementation.
async function unguarded(repo: any, id: string) {
  // ruleid: nestjs-ownership-id-only-find-one
  return repo.findOneBy({id});
}
async function priorGuard(repo: any, id: string, principal: any) {
  await assertAccess(principal, id);
  // ruleid: nestjs-ownership-id-only-find-one
  return repo.findOneBy({id});
}
async function differentShape(repo: any, slug: string) {
  // ok: nestjs-ownership-id-only-find-one
  return repo.findOneBy({slug});
}
// A prior guard still matches; its implementation must be reviewed in a product.
// No match for slug is a detector-shape negative, not proof of authorization.
