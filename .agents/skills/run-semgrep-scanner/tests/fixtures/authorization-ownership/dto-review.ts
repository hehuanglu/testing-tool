import { Body } from '@nestjs/common';
// ruleid: nestjs-ownership-user-id-field-in-dto
class RequestDto { ownerId: string; }
// ruleid: nestjs-ownership-user-id-field-in-dto
class ResponseDto { ownerId: string; }
// ruleid: nestjs-ownership-user-id-field-in-dto
class SharedDto { ownerId: string; }
// ok: nestjs-ownership-user-id-field-in-dto
class InheritedDto extends RequestDto { description: string; }
// ok: nestjs-ownership-user-id-field-in-dto
class OtherDto { label: string; }
// Aliasing and inheritance require mapping; no assumption that output cannot be input.
import { ResponseDto as ImportedInput } from './shared';
class Controller {
  create(@Body() input: RequestDto) { return input; }
  update(@Body() input: ImportedInput) { return input; }
  shared(@Body() input: SharedDto): SharedDto { return input; }
  inherited(@Body() input: InheritedDto) { return input; }
}
