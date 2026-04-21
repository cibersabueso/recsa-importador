import type { Codification } from '../value-objects/file/codification';
import type { ConfigurationStatus } from '../value-objects/file/configurationStatus';
import type { DecimalSeparator } from '../value-objects/file/decimalSeparator';
import type { Delimiter } from '../value-objects/file/delimiter';
import type { FileFormat } from '../value-objects/file/fileFormat';
import type { FileId } from '../value-objects/file/fileId';
import type { FileName } from '../value-objects/file/fileName.vo';
import type { FilePath } from '../value-objects/file/filePath';
import type { FileSize } from '../value-objects/file/fileSize';
import type { Key } from '../value-objects/file/key.vo';
import type { Process } from '../value-objects/file/process';
import type { SpreadSheet } from '../value-objects/file/spreadsheet';

export class File {
  private constructor(
    private readonly _id: FileId | null,
    private readonly _process: Process,
    private readonly _name: FileName,
    private readonly _format: FileFormat,
    private readonly _size: FileSize,
    private readonly _path: FilePath,
    private readonly _separator: DecimalSeparator | null,
    private readonly _codification: Codification | null,
    private readonly _delimiter: Delimiter | null,
    private readonly _spreadsheet: SpreadSheet | null,
    private readonly _configurationStatus: ConfigurationStatus,
    private readonly _key: Key | null,
  ) {}

  static create(
    id: FileId | null,
    process: Process,
    name: FileName,
    format: FileFormat,
    size: FileSize,
    path: FilePath,
    separator: DecimalSeparator | null,
    codification: Codification | null,
    delimiter: Delimiter | null,
    spreadsheet: SpreadSheet | null,
    configurationStatus: ConfigurationStatus,
    key: Key | null,
  ) {
    return new File(
      id,
      process,
      name,
      format,
      size,
      path,
      separator,
      codification,
      delimiter,
      spreadsheet,
      configurationStatus,
      key,
    );
  }

  id(): FileId | null {
    return this._id;
  }

  process(): Process {
    return this._process;
  }

  name(): FileName {
    return this._name;
  }

  format(): FileFormat {
    return this._format;
  }

  size(): FileSize {
    return this._size;
  }

  path(): FilePath {
    return this._path;
  }

  separator(): DecimalSeparator | null {
    return this._separator;
  }

  codification(): Codification | null {
    return this._codification;
  }

  delimiter(): Delimiter | null {
    return this._delimiter;
  }

  spreadsheet(): SpreadSheet | null {
    return this._spreadsheet;
  }

  isConfigurated(): boolean {
    return this._configurationStatus.value() === 'SI';
  }

  key(): Key | null {
    return this._key;
  }
}
