// Synthetic sink detection only. No sanitizer behavior is assumed.
function htmlRender(value: string) {
  // ruleid: react-public-dangerously-set-inner-html
  return <div dangerouslySetInnerHTML={{__html: value}} />;
}
function textRender(value: string) {
  // ok: react-public-dangerously-set-inner-html
  return <div>{value}</div>;
}
