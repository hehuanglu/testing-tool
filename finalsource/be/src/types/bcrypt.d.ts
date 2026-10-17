declare module 'bcrypt' {
  export function compare(data: string | Buffer, encrypted: string): Promise<boolean>;
  export function hash(data: string | Buffer, saltOrRounds: string | number): Promise<string>;
}
