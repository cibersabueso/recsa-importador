import { FileFactory } from "../../domain/factories/file.factory";
import { FileRepository } from "../../domain/ports/file.port";
import { UpdateFileDTO } from "../dtos/file/updateFileDTO";
import { FileResponse } from "../responses/file/file.response";

export class UpdateFileUseCase {

    constructor(private readonly repository: FileRepository){}

    async exec(dto: UpdateFileDTO, id: string): Promise<FileResponse> {

        const entity = FileFactory.fromPrimitives(
            id,
            dto.process_config,
            dto.name,
            dto.format,
            dto.size,
            dto.path,
            dto.delimiter,
            dto.encoding,
            dto.separator,
            dto.spreadsheet,
            true,
            null
        );

        const data = await this.repository.updateFile(entity);

        return new FileResponse(
            id,
            data.process().value(),
            data.name().value(),
            data.format().value(),
            data.size().value(),
            data.path().value(),
            data.separator()?.value() ?? null,
            data.codification()?.value() ?? null,
            data.delimiter()?.value() ?? null,
            data.spreadsheet()?.value() ?? null,
            data.isConfigurated(),
            data.key()?.value() ?? null
        );
    }
}