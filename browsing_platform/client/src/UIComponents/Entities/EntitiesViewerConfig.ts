type IEntityDisplayOption = "display" | "hide" | "collapse";
type IEntityAnnotatorOption = "show" | "hide";
type DeepPartial<T> = {
    [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

interface IEntityViewerConfig {
    account: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
    }
    post: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
    }
    media: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
        style?: React.CSSProperties;
    }
    mediaPart: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
        style?: React.CSSProperties;
    }
    archivingSession: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
    }
    comment: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
    }
    like: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
    }
}

export class EntityViewerConfig implements IEntityViewerConfig {
    account = {
        display: "display" as IEntityDisplayOption,
        annotator: "show" as IEntityAnnotatorOption,
    };
    post = {
        display: "display" as IEntityDisplayOption,
        annotator: "show" as IEntityAnnotatorOption,
    };
    media = {
        display: "display" as IEntityDisplayOption,
        annotator: "show" as IEntityAnnotatorOption,
        style: {} as React.CSSProperties,
    };
    mediaPart = {
        display: "collapse" as IEntityDisplayOption,
        annotator: "hide" as IEntityAnnotatorOption,
        style: {} as React.CSSProperties,
    };
    archivingSession = {
        display: "collapse" as IEntityDisplayOption,
        annotator: "hide" as IEntityAnnotatorOption,
    };
    comment = {
        display: "collapse" as IEntityDisplayOption,
        annotator: "hide" as IEntityAnnotatorOption,
    };
    like = {
        display: "collapse" as IEntityDisplayOption,
        annotator: "hide" as IEntityAnnotatorOption,
    };

    constructor(config?: DeepPartial<IEntityViewerConfig>) {
        if (config) {
            Object.keys(config).forEach((key) => {
                if (this.hasOwnProperty(key) && config[key as keyof IEntityViewerConfig]) {
                    Object.assign(this[key as keyof EntityViewerConfig], config[key as keyof IEntityViewerConfig]);
                }
            });
        }
    }
}