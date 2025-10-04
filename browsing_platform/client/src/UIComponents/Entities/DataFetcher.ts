import {ExtractedEntitiesNested} from "../../types/entities";
import server from "../../services/server";

export const fetchAccount = async (accountId: number): Promise<ExtractedEntitiesNested> => {
    return await server.get("account/" + accountId)
}