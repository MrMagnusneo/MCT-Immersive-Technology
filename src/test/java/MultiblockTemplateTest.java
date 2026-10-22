import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.util.zip.GZIPInputStream;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class MultiblockTemplateTest
{
	@Test
	void solidFuelBoilerDoesNotAttachAFluidPipeEntityToAnEngineeringBlock() throws Exception
	{
		try(var resource = getClass().getClassLoader().getResourceAsStream(
				"data/immersivetechnology/structure/multiblocks/boiler_solid.nbt"
		))
		{
			assertNotNull(resource, "Solid-fuel boiler structure must be packaged");
			try(var gzip = new GZIPInputStream(resource))
			{
				String nbtBytes = new String(gzip.readAllBytes(), StandardCharsets.ISO_8859_1);
				assertTrue(nbtBytes.contains("immersiveengineering:light_engineering"));
				assertFalse(
						nbtBytes.contains("immersiveengineering:fluidpipe"),
						"The boiler contains no fluid-pipe block, so it must not contain a fluid-pipe block entity"
				);
			}
		}
	}

	@Test
	void meltingCrucibleUsesRegisteredImmersiveEngineeringBlockEntityIds() throws Exception
	{
		try(var resource = getClass().getClassLoader().getResourceAsStream(
				"data/immersivetechnology/structure/multiblocks/melting_crucible.nbt"
		))
		{
			assertNotNull(resource, "Melting crucible structure must be packaged");
			try(var gzip = new GZIPInputStream(resource))
			{
				String nbtBytes = new String(gzip.readAllBytes(), StandardCharsets.ISO_8859_1);
				// Block names are furnace_heater/fluid_pipe, but IE registers their block entities without the underscore
				assertTrue(nbtBytes.contains("immersiveengineering:furnaceheater"), "Furnace heater block entity must use IE's furnaceheater id");
				assertTrue(nbtBytes.contains("immersiveengineering:fluidpipe"), "Fluid pipe block entity must use IE's fluidpipe id");
			}
		}
	}
}
