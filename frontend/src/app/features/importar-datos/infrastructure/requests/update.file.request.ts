export class UpdateFileRequest {
    constructor(
        public readonly name: string,
        public readonly process: string,
        public readonly format: string,
        public readonly path: string,
        public readonly size: number,
        public readonly separator: string,
        public readonly encoding: string,
        public readonly delimiter: string | null,
        public readonly spreadsheet: number | null,
        public readonly firstRowHeaders: boolean,
        public readonly key: string | null,
        public readonly position: number,
    ){}
}