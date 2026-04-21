import { File } from '../entities/file';
import { Codification } from '../value-objects/file/codification';
import { ConfigurationStatus } from '../value-objects/file/configurationStatus';
import { DecimalSeparator } from '../value-objects/file/decimalSeparator';
import { Delimiter } from '../value-objects/file/delimiter';
import { FileFormat } from '../value-objects/file/fileFormat';
import { FileId } from '../value-objects/file/fileId';
import { FileName } from '../value-objects/file/fileName.vo';
import { FilePath } from '../value-objects/file/filePath';
import { FileSize } from '../value-objects/file/fileSize';
import { Key } from '../value-objects/file/key.vo';
import { Process } from '../value-objects/file/process';
import { SpreadSheet } from '../value-objects/file/spreadsheet';

export class FileFactory {
  static fromPrimitives(
    id: string | null,
    process: string,
    name: string,
    format: string,
    size: number,
    path: string,
    delimiter: string | null,
    codification: string | null,
    separator: string | null,
    spreadsheet: number | null,
    status: boolean,
    key: string | null,
  ): File {
    return File.create(
      id ? FileId.create(id) : null,
      Process.create(process),
      FileName.create(name),
      FileFormat.create(format),
      FileSize.create(size),
      FilePath.create(path),
      separator ? DecimalSeparator.create(separator) : null,
      codification ? Codification.create(codification) : null,
      delimiter ? Delimiter.create(delimiter) : null,
      spreadsheet ? SpreadSheet.create(spreadsheet) : null,
      ConfigurationStatus.create(status),
      key ? Key.create(key) : null,
    );
  }
}
