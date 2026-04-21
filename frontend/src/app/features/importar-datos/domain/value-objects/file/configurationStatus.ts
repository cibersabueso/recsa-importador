export class ConfigurationStatus {
  private constructor(private readonly _value: ConfigurationStatusType) {}

  public static create(value: boolean): ConfigurationStatus {
    return new ConfigurationStatus(value ? 'SI' : 'NO');
  }

  value(): ConfigurationStatusType {
    return this._value;
  }
}

type ConfigurationStatusType = 'SI' | 'NO';
